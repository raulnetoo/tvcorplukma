# sheets.py
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from typing import List, Dict
from gspread.exceptions import WorksheetNotFound, APIError

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

REQUIRED_SA_KEYS = {
    "type","project_id","private_key_id","private_key","client_email","client_id",
    "auth_uri","token_uri","auth_provider_x509_cert_url","client_x509_cert_url"
}

@st.cache_resource(show_spinner=False)
def get_gs_client():
    if "gcp_service_account" not in st.secrets:
        raise RuntimeError("Faltou [gcp_service_account] em secrets.toml")
    if "spreadsheet_id" not in st.secrets or not str(st.secrets["spreadsheet_id"]).strip():
        raise RuntimeError("Faltou 'spreadsheet_id' em secrets.toml")

    sa_info = dict(st.secrets["gcp_service_account"])
    missing = REQUIRED_SA_KEYS.difference(sa_info.keys())
    if missing:
        raise RuntimeError("Chaves ausentes na Service Account: " + ", ".join(sorted(missing)))

    # normaliza \n da private_key se colaram multi-linha
    pk = sa_info.get("private_key","")
    if "\\n" not in pk and "BEGIN PRIVATE KEY" in pk:
        sa_info["private_key"] = pk.replace("\r\n","\n").replace("\n","\\n")

    credentials = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    return gspread.authorize(credentials)

@st.cache_resource(show_spinner=False)
def get_spreadsheet():
    client = get_gs_client()
    try:
        return client.open_by_key(st.secrets["spreadsheet_id"])
    except APIError as e:
        # dicas mais claras
        raise RuntimeError(
            "Falha ao abrir a planilha. Verifique:\n"
            "• O spreadsheet_id está correto\n"
            "• A planilha foi compartilhada como **Editor** com o client_email da Service Account\n"
            "• Google Sheets API e Drive API estão habilitadas no projeto GCP"
        ) from e

HEADER_CACHE: Dict[str, List[str]] = {}

def _safe_get_header(ws) -> list:
    """Lê a linha 1 com tolerância (se vazia, retorna [])."""
    try:
        rows = ws.get('1:1')  # [[col1, col2, ...]] ou []
        if rows and len(rows) > 0:
            return rows[0]
        return []
    except APIError as e:
        raise RuntimeError(
            f"Erro ao ler cabeçalho da aba '{ws.title}'. "
            "Confirme permissões/compartilhamento e tente novamente."
        ) from e

def _ensure_headers(ws, headers: List[str]):
    """Garante que a linha 1 contenha exatamente 'headers'."""
    existing = _safe_get_header(ws)
    if existing != headers:
        # Limpa e escreve cabeçalho
        ws.batch_clear(["1:1"])
        ws.update("1:1", [headers])

def get_ws(name: str, headers: List[str]):
    """Abre ou cria a worksheet e garante o cabeçalho."""
    sh = get_spreadsheet()
    try:
        ws = sh.worksheet(name)
    except WorksheetNotFound:
        # cria com tamanho mínimo
        ws = sh.add_worksheet(title=name, rows=1000, cols=max(10, len(headers)))
        ws.update("1:1", [headers])
        HEADER_CACHE[name] = headers
        return ws
    except APIError as e:
        raise RuntimeError(
            f"Não foi possível acessar a aba '{name}'. "
            "Cheque se a planilha está compartilhada como **Editor** com a Service Account."
        ) from e

    # garante headers
    _ensure_headers(ws, headers)
    HEADER_CACHE[name] = headers
    return ws

def read_df(name: str, headers: List[str]) -> pd.DataFrame:
    ws = get_ws(name, headers)
    try:
        values = ws.get_all_records()  # respeita a primeira linha como header
    except APIError as e:
        raise RuntimeError(
            f"Erro ao ler dados da aba '{name}'. "
            "Se a planilha acabou de ser criada, abra o admin e salve ao menos uma vez para gerar as abas."
        ) from e

    df = pd.DataFrame(values)
    for h in headers:
        if h not in df.columns:
            df[h] = None
    return df[headers] if headers else df

def write_df(name: str, headers: List[str], df: pd.DataFrame):
    ws = get_ws(name, headers)
    try:
        ws.clear()
        ws.update("1:1", [headers])
        if not df.empty:
            data = df.fillna("").astype(str).values.tolist()
            ws.update("A2", data)
    except APIError as e:
        raise RuntimeError(
            f"Erro ao escrever na aba '{name}'. "
            "Verifique permissões e se não há proteção de intervalo bloqueando escrita."
        ) from e
