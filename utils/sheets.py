import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from typing import List, Dict


SCOPES = [
"https://www.googleapis.com/auth/spreadsheets",
"https://www.googleapis.com/auth/drive",
]


@st.cache_resource(show_spinner=False)
def get_gs_client():
sa_info = st.secrets["gcp_service_account"]
credentials = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
return gspread.authorize(credentials)


@st.cache_resource(show_spinner=False)
def get_spreadsheet():
client = get_gs_client()
return client.open_by_key(st.secrets["spreadsheet_id"])


HEADER_CACHE = {}


def get_ws(name: str, headers: List[str]):
"""Open or create worksheet with ensured headers."""
sh = get_spreadsheet()
try:
ws = sh.worksheet(name)
except gspread.WorksheetNotFound:
ws = sh.add_worksheet(title=name, rows=1000, cols=max(10, len(headers)))
ws.append_row(headers)
HEADER_CACHE[name] = headers
return ws


# ensure headers
existing = ws.row_values(1)
if existing != headers:
# rewrite header row to match expected schema
ws.update("1:1", [headers])
HEADER_CACHE[name] = headers
return ws


def read_df(name: str, headers: List[str]) -> pd.DataFrame:
ws = get_ws(name, headers)
values = ws.get_all_records()
df = pd.DataFrame(values)
# guarantee all expected columns exist
for h in headers:
if h not in df.columns:
df[h] = None
return df[headers]


def write_df(name: str, headers: List[str], df: pd.DataFrame):
ws = get_ws(name, headers)
ws.clear()
ws.append_row(headers)
if not df.empty:
ws.update(f"A2", [df.fillna("").astype(str).values.tolist()[0]] if len(df)==1 else df.fillna("").astype(str).values.tolist())


def upsert_row(name: str, headers: List[str], row: Dict, key_col: str = "id"):
df = read_df(name, headers)
if key_col in df.columns and str(row.get(key_col, "")).strip() != "":
key = str(row[key_col])
if key in df[key_col].astype(str).values:
df.loc[df[key_col].astype(str) == key, list(row.keys())] = list(row.values())
else:
df.loc[len(df)] = [row.get(h, None) for h in headers]
else:
# assign next id
next_id = 1 if df.empty else int(pd.to_numeric(df[key_col], errors='coerce').fillna(0).max()) + 1
row[key_col] = next_id
df.loc[len(df)] = [row.get(h, None) for h in headers]
# keep order
if 'order' in df.columns:
df['order'] = pd.to_numeric(df['order'], errors='coerce').fillna(0).astype(int)
df = df.sort_values('order')
write_df(name, headers, df)
return row