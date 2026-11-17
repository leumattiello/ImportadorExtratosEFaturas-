"""Autenticacao e leitura/gravação conservadora na planilha privada."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import tempfile

from .identidade import Lancamento

MESES = ("Janeiro","Fevereiro","Março","Abril","Maio","Junho",
         "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro")
CABECALHO = ("Data","Descrição","Debito","Credito","Valor","ID")
ESCOPO = ("https://www.googleapis.com/auth/spreadsheets",)

class ErroPlanilha(Exception):
    """Nunca divulga tokens ou conteudo bancario em mensagens."""

@dataclass(frozen=True)
class Instantaneo:
    existentes: tuple[Lancamento,...]
    contas: frozenset[str]
    proximas: dict[str,int]
    ids_abas: dict[str,int]
    limites: dict[str,int]
    assinatura: str

@dataclass(frozen=True)
class LinhaNova:
    data: date
    descricao: str
    valor_origem: Decimal
    id_lancamento: str
    conta_planilha: str
    categoria: str

def _validar_privado(arquivo: Path, existe: bool) -> Path:
    arquivo = Path(arquivo).expanduser()
    raiz = Path(__file__).resolve().parents[2]
    resolvido = arquivo.resolve()
    if arquivo.is_symlink() or resolvido == raiz or raiz in resolvido.parents:
        raise ErroPlanilha("Arquivos OAuth devem ficar fora do repositorio, sem links.")
    if existe:
        try:
            info = arquivo.stat()
        except OSError as exc:
            raise ErroPlanilha("Arquivo OAuth privado nao encontrado.") from exc
        if not stat.S_ISREG(info.st_mode) or info.st_size > 1024*1024:
            raise ErroPlanilha("Arquivo OAuth invalido.")
        if os.name == "posix" and stat.S_IMODE(info.st_mode) & 0o077:
            raise ErroPlanilha("Aplique chmod 600 aos arquivos OAuth.")
    return arquivo

def autenticar(client: Path, token: Path):
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise ErroPlanilha("Instale requirements-google.txt no ambiente virtual.") from exc
    client = _validar_privado(client, True)
    token = _validar_privado(token, token.exists() or token.is_symlink())
    try:
        auth = Credentials.from_authorized_user_file(str(token), list(ESCOPO)) if token.exists() else None
        if auth and not auth.has_scopes(ESCOPO):
            auth = None
        if not auth or not auth.valid:
            if auth and auth.expired and auth.refresh_token:
                auth.refresh(Request())
            else:
                fluxo = InstalledAppFlow.from_client_secrets_file(str(client), scopes=list(ESCOPO))
                auth = fluxo.run_local_server(port=0)
            if not auth.has_scopes(ESCOPO):
                raise ErroPlanilha("Escopo de planilhas nao autorizado.")
            if not token.parent.is_dir():
                raise ErroPlanilha("Diretorio privado de tokens nao existe.")
            temp = None
            try:
                with tempfile.NamedTemporaryFile("w",encoding="utf-8",dir=token.parent,
                                                 prefix=".token-",delete=False) as f:
                    temp = Path(f.name)
                    os.chmod(temp,0o600)
                    f.write(auth.to_json())
                os.replace(temp,token)
            finally:
                if temp and temp.exists():
                    temp.unlink()
        return build("sheets","v4",credentials=auth,cache_discovery=False)
    except ErroPlanilha:
        raise
    except Exception as exc:
        raise ErroPlanilha("Falha OAuth; confira credenciais, acesso e conexao.") from exc

def _data(valor):
    if isinstance(valor,(float,int)) and not isinstance(valor,bool):
        return date(1899,12,30) + timedelta(days=int(valor))
    if isinstance(valor,str):
        for fmt in ("%d/%m/%Y","%d/%m/%y","%Y-%m-%d"):
            try:
                return datetime.strptime(valor.strip(),fmt).date()
            except ValueError:
                pass
    raise ErroPlanilha("Data existente invalida.")

def _valor(valor):
    try:
        if isinstance(valor,bool):
            raise ValueError()
        if isinstance(valor,(float,int)):
            res=Decimal(str(valor))
        elif isinstance(valor,str):
            raw=valor.strip().replace("R$","").replace(" ","")
            if "," in raw:
                raw=raw.replace(".","").replace(",",".")
            res=Decimal(raw)
        else:
            raise ValueError()
        if not res.is_finite(): raise ValueError()
        return abs(res)
    except (InvalidOperation,ValueError) as exc:
        raise ErroPlanilha("Valor existente invalido.") from exc

def _linha(valores):
    x=list(valores[:6])+[""]*max(0,6-len(valores))
    if not any(v not in ("",None) for v in x): return None
    a,b,c,d,e,f=x
    if not a or not isinstance(b,str) or not b.strip() or e in ("",None):
        raise ErroPlanilha("Lancamento historico incompleto em A:F.")
    if not isinstance(c,str) or not isinstance(d,str) or not c.strip() or not d.strip():
        raise ErroPlanilha("Debito/credito existente incompleto em A:F.")
    if f is not None and not isinstance(f,str):
        raise ErroPlanilha("ID existente nao e texto.")
    return Lancamento(_data(a),b,_valor(e),f or None)

def ler_instantaneo(servico, planilha_id: str) -> Instantaneo:
    try:
        api=servico.spreadsheets()
        meta=api.get(spreadsheetId=planilha_id,
            fields="sheets(properties(sheetId,title,gridProperties(rowCount)))").execute()
        infos={s["properties"]["title"]:s["properties"] for s in meta.get("sheets",[])}
        if any(m not in infos for m in MESES) or "Dados" not in infos:
            raise ErroPlanilha("Planilha sem as 12 abas mensais ou aba Dados.")
        if any(not 3<=infos[m]["gridProperties"]["rowCount"]<=10000 for m in MESES):
            raise ErroPlanilha("Quantidade de linhas fora do limite de seguranca.")
        ranges=[f"'{m}'!A2:F{infos[m]['gridProperties']['rowCount']}" for m in MESES]
        ranges.append("'Dados'!A3:A200")
        blocos=api.values().batchGet(spreadsheetId=planilha_id,ranges=ranges,
            valueRenderOption="UNFORMATTED_VALUE",
            dateTimeRenderOption="FORMATTED_STRING").execute().get("valueRanges",[])
        if len(blocos)!=13: raise ErroPlanilha("Leitura incompleta da planilha.")
        existentes=[];proximas={};ids={};limites={}
        for k,mes in enumerate(MESES):
            rows=blocos[k].get("values",[])
            if not rows or tuple(str(v) for v in rows[0][:6])!=CABECALHO:
                raise ErroPlanilha("Cabecalho A2:F2 incompativel.")
            ultima=2
            for nro,row in enumerate(rows[1:],start=3):
                if any(v not in ("",None) for v in row[:6]):
                    ultima=nro
                reg=_linha(row)
                if reg: existentes.append(reg)
            proximas[mes]=ultima
            ids[mes]=int(infos[mes]["sheetId"])
            limites[mes]=int(infos[mes]["gridProperties"]["rowCount"])
        contas=frozenset(r[0].strip() for r in blocos[12].get("values",[])
                          if r and isinstance(r[0],str) and r[0].strip())
        assinatura=sha256(json.dumps({"blocos":blocos,"info":infos},
                          sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        return Instantaneo(tuple(existentes),contas,proximas,ids,limites,assinatura)
    except ErroPlanilha: raise
    except Exception as exc:
        raise ErroPlanilha("Nao foi possivel ler a planilha Google.") from exc

def gravar_lote(servico,planilha_id,original,mes,linhas):
    """Releitura antes do batch; nunca sobrescreve linhas existentes."""
    if not 1<=mes<=12:raise ErroPlanilha("Mes invalido.")
    if not linhas:return 0
    ids=[x.id_lancamento for x in linhas]
    if any(not isinstance(i,str) or not i.startswith("AUTO:") for i in ids) or len(ids)!=len(set(ids)):
        raise ErroPlanilha("IDs invalidos ou repetidos no lote.")
    atual=ler_instantaneo(servico,planilha_id)
    if atual.assinatura!=original.assinatura:
        raise ErroPlanilha("A planilha mudou durante a revisao; execute novamente.")
    presentes={m.identificador for m in atual.existentes if m.identificador}
    if any(i in presentes for i in ids):
        raise ErroPlanilha("ID do lote ja existe na planilha.")
    nome=MESES[mes-1]
    pos=atual.proximas[nome]
    if pos+len(linhas)>atual.limites[nome]:
        raise ErroPlanilha("Nao ha linhas livres suficientes.")
    requests=[]
    for linha in linhas:
        if linha.conta_planilha not in atual.contas or linha.categoria not in atual.contas:
            raise ErroPlanilha("Conta ou categoria ausente da aba Dados.")
        if linha.conta_planilha==linha.categoria:
            raise ErroPlanilha("Conta e contrapartida nao podem ser iguais.")
        valor=linha.valor_origem
        if not isinstance(valor,Decimal) or not valor.is_finite() or not valor or valor.as_tuple().exponent < -2:
            raise ErroPlanilha("Valor invalido ou com mais de duas casas.")
        debito,credito=((linha.conta_planilha,linha.categoria) if valor<0
                        else (linha.categoria,linha.conta_planilha))
        serial=(linha.data-date(1899,12,30)).days
        texto=lambda t:{"userEnteredValue":{"stringValue":t}}
        celulas=[{"userEnteredValue":{"numberValue":serial}},texto(linha.descricao),
                 texto(debito),texto(credito),
                 {"userEnteredValue":{"numberValue":float(abs(valor))}},
                 texto(linha.id_lancamento)]
        requests.append({"updateCells":{"range":{"sheetId":atual.ids_abas[nome],
                 "startRowIndex":pos,"endRowIndex":pos+1,"startColumnIndex":0,"endColumnIndex":6},
                 "rows":[{"values":celulas}],"fields":"userEnteredValue"}})
        pos+=1
    try:
        servico.spreadsheets().batchUpdate(spreadsheetId=planilha_id,
                                          body={"requests":requests}).execute()
    except Exception as exc:
        raise ErroPlanilha("Gravacao nao confirmada; confira a planilha antes de repetir.") from exc
    final=ler_instantaneo(servico,planilha_id)
    finais={m.identificador for m in final.existentes if m.identificador}
    if any(i not in finais for i in ids):
        raise ErroPlanilha("Gravacao enviada, confirmacao incompleta; nao repita sem conferir.")
    return len(linhas)
