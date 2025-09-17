import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from typing import List, Dict
from gspread.exceptions import WorksheetNotFound, APIError
import json

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADER_CACHE: Dict[str, List[str]] = {}

@st.cache_resource(show_spinner=False)
def get_gs_client():
    """
    Lê os secrets (Streamlit Cloud), aceita:
    - gcp_service_account como dict TOML
    - gcp_service_account como string JSON (faz json.loads)
    E normaliza a private_key (multilinha ou com \\n), validando antes de autorizar.
    """
    if "spreadsheet_id" not in st.secrets or not str(st.secrets["spreadsheet_id"]).strip():
        raise RuntimeError("Faltou 'spreadsheet_id' em Secrets.")

    if "gcp_service_account" not in st.secrets:
        raise RuntimeError("Faltou seção [gcp_service_account] em Secrets.")

    sa_info = st.secrets["gcp_service_account"]

    # Se colaram JSON como string, tenta parse
    if isinstance(sa_info, str):
        try:
            sa_info = json.loads(sa_info)
        except Exception as e:
            raise RuntimeError("gcp_service_account em Secrets é string mas não é JSON válido.") from e

    sa_info = dict(sa_info)  # mutável

    required = {
        "type","project_id","private_key_id","private_key","client_email","client_id",
        "auth_uri","token_uri","auth_provider_x509_cert_url","client_x509_cert_url"
    }
    missing = required.difference(sa_info.keys())
    if missing:
        raise RuntimeError("Chaves ausentes na Service Account: " + ", ".join(sorted(missing)))

    # Normaliza private_key
    pk = str(sa_info.get("private_key", "")).strip()
    if "\\n" in pk:  # veio em uma linha com \n
        pk = pk.replace("\\n", "\n")
    pk = pk.replace("\r\n", "\n").replace("\r", "\n").strip()

    # Remove aspas acidentais
    if (pk.startswith('"') and pk.endswith('"')) or (pk.startswith("'") and pk.endswith("'")):
        pk = pk[1:-1].strip()

    # Sanity checks
    if not pk.startswith("-----BEGIN PRIVATE KEY-----"):
        raise RuntimeError("private_key inválida: não inicia com '-----BEGIN PRIVATE KEY-----'.")
    if not pk.endswith("-----END PRIVATE KEY-----"):
        raise RuntimeError("private_key inválida: não termina com '-----END PRIVATE KEY-----'.")
    if "\n" not in pk:
        raise RuntimeError("private_key inválida: não há quebras de linha reais. Use multiline (\"\"\"...\"\"\") ou \\n.")

    sa_info["private_key"] = pk

    try:
        credentials = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        raise RuntimeError(
            "Falha ao criar credenciais do Google. "
            "Verifique a private_key (formato), se a planilha está compartilhada como **Editor** com o client_email "
            "e se as APIs Sheets/Drive estão habilitadas no GCP."
        ) from e

@st.cache_resource(show_spinner=False)
def get_spreadsheet():
    client = get_gs_client()
    try:
        return client.open_by_key(st.secrets["spreadsheet_id"])
    except APIError as e:
        raise RuntimeError(
            "Falha ao abrir a planilha. Verifique:\n"
            "• O spreadsheet_id está correto\n"
            "• A planilha foi compartilhada como **Editor** com o client_email da Service Account\n"
            "• Google Sheets API e Drive API estão habilitadas no projeto GCP"
        ) from e

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
        ws.batch_clear(["1:1"])
        ws.update("1:1", [headers])

def get_ws(name: str, headers: List[str]):
    """Abre ou cria a worksheet e garante o cabeçalho."""
    sh = get_spreadsheet()
    try:
        ws = sh.worksheet(name)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title=name, rows=1000, cols=max(10, len(headers)))
        ws.update("1:1", [headers])
        HEADER_CACHE[name] = headers
        return ws
    except APIError as e:
        raise RuntimeError(
            f"Não foi possível acessar a aba '{name}'. "
            "Cheque se a planilha está compartilhada como **Editor** com a Service Account."
        ) from e

    _ensure_headers(ws, headers)
    HEADER_CACHE[name] = headers
    return ws

def read_df(name: str, headers: List[str]) -> pd.DataFrame:
    ws = get_ws(name, headers)
    try:
        values = ws.get_all_records()  # respeita a linha 1 como header
    except APIError as e:
        raise RuntimeError(
            f"Erro ao ler dados da aba '{name}'. "
            "Se a planilha acabou de ser criada, abra o admin e salve ao menos uma vez para gerar as abas."
        ) from e

    df = pd.DataFrame(values)
    # garante colunas esperadas
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

def upsert_row(name: str, headers: List[str], row: Dict, key_col: str = "id"):
    df = read_df(name, headers)
    if key_col in df.columns and str(row.get(key_col, "")).strip() != "":
        key = str(row[key_col])
        if key in df[key_col].astype(str).values:
            # update
            for k, v in row.items():
                if k in df.columns:
                    df.loc[df[key_col].astype(str) == key, k] = v
        else:
            # insert
            df.loc[len(df)] = [row.get(h, None) for h in headers]
    else:
        # gera próximo id
        if "id" in df.columns:
            next_id = 1 if df.empty else int(pd.to_numeric(df["id"], errors="coerce").fillna(0).max()) + 1
            row["id"] = next_id
        df.loc[len(df)] = [row.get(h, None) for h in headers]

    if "order" in df.columns:
        df["order"] = pd.to_numeric(df["order"], errors="coerce").fillna(0).astype(int)
        df = df.sort_values("order")
    write_df(name, headers, df)
    return row
