"""Revisao interativa de um arquivo antes da gravacao controlada."""
from dataclasses import dataclass
from collections import Counter
from pathlib import Path
import re
import sys

from .identidade import Lancamento, ErroIdentidade, analisar_identificadores
from .identificadores_derivados import gerar_candidatos, proxima_ocorrencia
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
    ids_aprovados: tuple[str,...] = ()

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
    movimentos=tuple(movimentos)
    candidatos=[Lancamento(m.data,m.descricao,abs(m.valor),m.identificador)
                for m in movimentos]
    try:
        avaliados=analisar_identificadores(candidatos,existentes,
                   origem=origem,conta=conta,id_externo_confiavel=confiavel)
        identidades=gerar_candidatos(movimentos,origem,conta,
                                     id_externo_confiavel=confiavel)
    except ErroIdentidade as exc:
        raise ErroFluxo(str(exc)) from exc
    ids_existentes={m.identificador for m in existentes if m.identificador}
    # Tambem considerar lancamentos historicos sem ID e outras origens.
    # So data/valor nao prova igualdade, mas impede confirmacao automatica.
    dados_existentes={(m.data,abs(m.valor)) for m in existentes}
    # A identidade derivada representa uma possibilidade, nao prova de igualdade.
    totais=Counter(i.base for i in identidades if i.derivado)
    contagens={"NOVO":0,"JA_EXISTENTE":0,"CONFLITO":0,"REVISAR":0}
    aceitos=set();aprovados=[];ids_aprovados=[]
    ignorados=bloqueados=0
    for indice,(mov,r,identidade) in enumerate(zip(movimentos,avaliados,identidades)):
        ident=identidade.identificador
        reserva=ids_existentes | aceitos
        if identidade.derivado:
            base=identidade.base
            repetido_no_arquivo=totais[base]>1
            possivel_historico=(mov.data,abs(mov.valor)) in dados_existentes
            ja_importado=any(i.startswith(base+":") for i in ids_existentes)
            ja_aprovado=any(i.startswith(base+":") for i in aceitos)
            # Mesmo fingerprint em arquivo sobreposto e ambiguo.
            # -y NUNCA cria uma nova ocorrencia indistinguivel.
            if ja_importado or ja_aprovado:
                contagens["REVISAR"]+=1
                if assumir_sim:
                    bloqueados+=1
                    continue
                if exige_tty and not sys.stdin.isatty():
                    raise ErroFluxo("Revisao requer terminal ou --assumir-sim.")
                pergunta=(f"{mov.data:%d/%m/%Y} | {mov.descricao[:32]} | "
                          f"R$ {mov.valor:.2f} | Possivel reimportacao; "
                          "confirmar NOVA transacao distinta? [s/N] ")
                if not confirmar(pergunta,entrada=entrada,padrao_sim=False):
                    ignorados+=1
                    continue
                try:
                    ident=proxima_ocorrencia(base,reserva)
                except ErroIdentidade as exc:
                    raise ErroFluxo(str(exc)) from exc
            elif repetido_no_arquivo:
                contagens["REVISAR"]+=1
                if assumir_sim:
                    bloqueados+=1
                    continue
                if exige_tty and not sys.stdin.isatty():
                    raise ErroFluxo("Revisao requer terminal ou --assumir-sim.")
                pergunta=(f"{mov.data:%d/%m/%Y} | {mov.descricao[:32]} | "
                          f"R$ {mov.valor:.2f} | Movimentos indistinguiveis; "
                          "confirmar como distinto? [s/N] ")
                if not confirmar(pergunta,entrada=entrada,padrao_sim=False):
                    ignorados+=1
                    continue
                ident=proxima_ocorrencia(base,reserva)
            else:
                # Sem sobreposicao exata por fingerprint, ainda exige revisao.
                contagens["REVISAR"]+=1
                if possivel_historico and assumir_sim:
                    bloqueados+=1
                    continue
                if exige_tty and not assumir_sim and not sys.stdin.isatty():
                    raise ErroFluxo("Revisao requer terminal ou --assumir-sim.")
                resumo=f"{mov.data:%d/%m/%Y} | {mov.descricao[:32]} | R$ {mov.valor:.2f}"
                if not confirmar(f"{resumo} | ID derivado: importar? [S/n] ",
                                 assumir_sim=assumir_sim,entrada=entrada):
                    ignorados+=1
                    continue
                if ident in reserva:
                    bloqueados+=1
                    continue
        else:
            contagens[r.situacao]+=1
            if r.situacao=="JA_EXISTENTE":
                ignorados+=1
                continue
            if (r.situacao=="CONFLITO" or ident is None
                    or ident in reserva or r.motivo=="id_repetido_no_lote"):
                bloqueados+=1
                continue
            if r.situacao=="REVISAR":
                if r.motivo=="possivel_sobreposicao" and assumir_sim:
                    bloqueados+=1
                    continue
                if exige_tty and not assumir_sim and not sys.stdin.isatty():
                    raise ErroFluxo("Revisao requer terminal ou --assumir-sim.")
                resumo=f"{mov.data:%d/%m/%Y} | {mov.descricao[:32]} | R$ {mov.valor:.2f}"
                if not confirmar(f"{resumo} | {r.motivo}: importar? [S/n] ",
                                 assumir_sim=assumir_sim,entrada=entrada):
                    ignorados+=1
                    continue
        if not ident or ident in reserva:
            bloqueados+=1
            continue
        aprovados.append(indice)
        ids_aprovados.append(ident)
        aceitos.add(ident)
    return Previa(contagens["NOVO"],contagens["JA_EXISTENTE"],contagens["CONFLITO"],
                  contagens["REVISAR"],tuple(aprovados),ignorados,bloqueados,
                  tuple(ids_aprovados))

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
        for i,ident in zip(previa.aprovados,previa.ids_aprovados):
            m=movimentos[i]
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
