"""Revisao interativa de um arquivo antes da gravacao controlada."""
from dataclasses import dataclass
from pathlib import Path
import re
import sys

from .identidade import Lancamento, ErroIdentidade, analisar_identificadores, gerar_id_automatico
from .leitor_csv import ColunasCSV, ErroCSV, ler_csv
from .ofx import ErroOFX, ler_ofx
from .perfis_csv import ErroPerfis, ler_perfis, selecionar_perfil
from .sheets_gateway import ErroPlanilha, LinhaNova, autenticar, ler_instantaneo, gravar_lote

class ErroFluxo(Exception):
    """Falha controlada; dados bancarios nao aparecem em mensagens de erro."""

@dataclass(frozen=True)
class Previa:
    novos: int
    existentes: int
    conflitos: int
    revisao: int
    aprovados: tuple[int,...]
    ignorados: int
    bloqueados: int

def confirmar(pergunta, *, assumir_sim=False, entrada=input, padrao_sim=True):
    """Enter responde S em revisoes; no aceite final, Enter responde N."""
    if assumir_sim:return True
    for tentativa in range(5):
        try:
            resposta=entrada(pergunta).strip().casefold()
        except (EOFError,KeyboardInterrupt) as exc:
            raise ErroFluxo("Revisao interrompida; nada foi gravado.") from exc
        if resposta=="":return padrao_sim
        if resposta in ("s","sim"):return True
        if resposta in ("n","nao","não"):return False
        print("Responda S ou n.")
    raise ErroFluxo("Respostas invalidas; nada foi gravado.")

def preparar_previa(movimentos,existentes,origem,conta,confiavel,*,
                    assumir_sim=False,entrada=input,exige_tty=True):
    candidatos=[Lancamento(m.data,m.descricao,abs(m.valor),m.identificador)
                for m in movimentos]
    try:
        avaliados=analisar_identificadores(candidatos,existentes,
                   origem=origem,conta=conta,id_externo_confiavel=confiavel)
    except ErroIdentidade as exc:
        raise ErroFluxo(str(exc)) from exc
    contagens={s:sum(r.situacao==s for r in avaliados)
               for s in ("NOVO","JA_EXISTENTE","CONFLITO","REVISAR")}
    ids_existentes={m.identificador for m in existentes if m.identificador}
    aceitos=set()
    aprovados=[];ignorados=bloqueados=0
    for i,(mov,r) in enumerate(zip(movimentos,avaliados)):
        if r.situacao=="JA_EXISTENTE":
            ignorados+=1
            continue
        # Nao se pode solucionar estes conflitos com resposta S.
        if (r.situacao=="CONFLITO" or r.id_proposto is None
              or r.id_proposto in ids_existentes
              or r.id_proposto in aceitos
              or r.motivo=="id_repetido_no_lote"):
            bloqueados+=1
            continue
        if r.situacao=="REVISAR":
            if exige_tty and not assumir_sim and not sys.stdin.isatty():
                raise ErroFluxo("Revisao requer terminal ou --assumir-sim.")
            resumo=f"{mov.data:%d/%m/%Y} | {mov.descricao[:32]} | R$ {mov.valor:.2f}"
            if not confirmar(f"{resumo} | {r.motivo}: importar? [S/n] ",
                             assumir_sim=assumir_sim,entrada=entrada):
                ignorados+=1
                continue
        aprovados.append(i)
        aceitos.add(r.id_proposto)
    return Previa(contagens["NOVO"],contagens["JA_EXISTENTE"],contagens["CONFLITO"],
                  contagens["REVISAR"],tuple(aprovados),ignorados,bloqueados)

def _fonte(pasta,arquivo,ano):
    pasta=Path(pasta).expanduser()
    arquivo=Path(arquivo).expanduser()
    if pasta.is_symlink() or arquivo.is_symlink() or not arquivo.is_file():
        raise ErroFluxo("Arquivo de entrada invalido ou link simbolico.")
    try:
        rel=arquivo.resolve(strict=True).relative_to(pasta.resolve(strict=True))
    except (ValueError,OSError) as exc:
        raise ErroFluxo("Arquivo deve estar na pasta anual privada.") from exc
    if len(rel.parts)!=2 or rel.parts[0]!=str(ano):
        raise ErroFluxo("Arquivo nao corresponde ao ano de competencia.")
    if arquivo.suffix.lower() not in (".ofx",".csv"):
        raise ErroFluxo("Somente OFX/CSV sao suportados na importacao.")
    return arquivo

def _ler(arquivo,args,pasta):
    if arquivo.suffix.lower()==".ofx":
        return ler_ofx(arquivo)
    colunas=ColunasCSV(**{campo:getattr(args,"csv_coluna_"+campo)
                  for campo in ("data","descricao","valor","credito","debito","identificador")})
    manual=(args.csv_delimitador is not None or args.csv_pular_linhas!=0
            or any(getattr(colunas,campo) is not None for campo
                   in ("data","descricao","valor","credito","debito","identificador")))
    perfil_path=args.perfis or pasta.parent/"perfis.ini"
    if not args.sem_perfis and (args.perfis or perfil_path.exists()):
        if manual:
            raise ErroFluxo("Nao misture perfis CSV e mapeamento manual; use --sem-perfis.")
        perfil=selecionar_perfil(arquivo,ler_perfis(perfil_path))
        return ler_csv(arquivo,colunas=perfil.colunas,delimitador=perfil.delimitador,
                       pular_linhas=perfil.pular_linhas)
    return ler_csv(arquivo,colunas=colunas,delimitador=args.csv_delimitador,
                   pular_linhas=args.csv_pular_linhas)

def _categoria(m,contas,padrao,assumir_sim):
    if padrao:
        if padrao not in contas:
            raise ErroFluxo("Categoria nao encontrada na aba Dados.")
        return padrao
    if assumir_sim:
        raise ErroFluxo("--assumir-sim exige --categoria.")
    if not sys.stdin.isatty():
        raise ErroFluxo("Classificacao requer terminal ou --categoria.")
    for tentativa in range(5):
        try:
            resposta=input(f"{m.data:%d/%m/%Y} | {m.descricao[:28]}: categoria? ").strip()
        except (EOFError,KeyboardInterrupt) as exc:
            raise ErroFluxo("Classificacao interrompida; nenhuma gravacao.") from exc
        if resposta in contas:return resposta
        print("Digite exatamente uma categoria/conta da aba Dados.")
    raise ErroFluxo("Categoria invalida; nenhuma gravacao.")

def executar(args):
    """Um arquivo e um mes por execucao; nunca acessa dados bancarios publicamente."""
    pasta=Path(args.pasta).expanduser()
    arquivo=_fonte(pasta,args.arquivo,args.ano_competencia)
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,150}",args.planilha_id):
        raise ErroFluxo("ID da planilha invalido.")
    if not 1<=args.mes_competencia<=12:
        raise ErroFluxo("Mes de competencia invalido.")
    try:
        movimentos=_ler(arquivo,args,pasta)
        client=args.credenciais_google or pasta.parent/"google_client_secret.json"
        token=args.token_google or pasta.parent/"token_google.json"
        api=autenticar(client,token)
        estado=ler_instantaneo(api,args.planilha_id)
        confiavel=arquivo.suffix.lower()==".ofx" or args.id_confiavel
        previa=preparar_previa(movimentos,estado.existentes,
                     args.origem,args.conta,confiavel,assumir_sim=args.assumir_sim)
        print(f"Movimentacoes encontradas: {len(movimentos)}")
        print(f"Novas sem indicios: {previa.novos}")
        print(f"Ja existentes: {previa.existentes}")
        print(f"Conflitos de ID: {previa.conflitos}")
        print(f"Para revisao: {previa.revisao}")
        print(f"Aprovadas: {len(previa.aprovados)}")
        print(f"Ignoradas: {previa.ignorados}; bloqueadas: {previa.bloqueados}")
        if not args.importar:
            print("SIMULACAO: nenhum lancamento foi gravado.")
            return 0
        if previa.conflitos:
            raise ErroFluxo("Conflitos de ID detectados; importacao bloqueada.")
        if args.conta_planilha not in estado.contas:
            raise ErroFluxo("Conta nao encontrada na aba Dados.")
        if args.assumir_sim and not args.categoria:
            raise ErroFluxo("--assumir-sim requer --categoria para escrita.")
        linhas=[]
        for i in previa.aprovados:
            m=movimentos[i]
            ident=gerar_id_automatico(args.origem,args.conta,m.identificador)
            categoria=_categoria(m,estado.contas,args.categoria,args.assumir_sim)
            linhas.append(LinhaNova(m.data,m.descricao,m.valor,ident,
                                   args.conta_planilha,categoria))
        if not linhas:
            print("Nenhuma movimentacao elegivel para gravacao.")
            return 0
        if not confirmar(f"Gravar {len(linhas)} lancamentos na planilha? [s/N] ",
                         assumir_sim=args.assumir_sim,padrao_sim=False):
            print("Gravacao cancelada.")
            return 0
        n=gravar_lote(api,args.planilha_id,estado,args.mes_competencia,tuple(linhas))
        print(f"Importacao confirmada no Google Sheets: {n} lancamentos.")
        return 0
    except (ErroCSV,ErroOFX,ErroPerfis,ErroPlanilha,ErroIdentidade) as exc:
        raise ErroFluxo(str(exc)) from exc
