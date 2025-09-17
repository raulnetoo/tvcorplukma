import streamlit as st
import requests
from datetime import datetime, timezone
from dateutil import tz
from zoneinfo import ZoneInfo


@st.cache_data(ttl=60)
def fetch_fx_brl():
# USD/EUR via exchangerate.host (sem chave)
fx = {"USD": None, "EUR": None}
try:
r = requests.get("https://api.exchangerate.host/latest", params={"base": "USD", "symbols": "BRL"}, timeout=10)
r.raise_for_status()
fx["USD"] = float(r.json()["rates"]["BRL"]) # 1 USD em BRL
except Exception:
pass
try:
r = requests.get("https://api.exchangerate.host/latest", params={"base": "EUR", "symbols": "BRL"}, timeout=10)
r.raise_for_status()
fx["EUR"] = float(r.json()["rates"]["BRL"]) # 1 EUR em BRL
except Exception:
pass
return fx


@st.cache_data(ttl=60)
def fetch_crypto_brl():
# Coingecko simples
out = {"BTC": None, "ETH": None}
try:
r = requests.get("https://api.coingecko.com/api/v3/simple/price", params={"ids":"bitcoin,ethereum","vs_currencies":"brl"}, timeout=10)
r.raise_for_status()
js = r.json()
out["BTC"] = float(js.get("bitcoin",{}).get("brl"))
out["ETH"] = float(js.get("ethereum",{}).get("brl"))
except Exception:
pass
return out


@st.cache_data(ttl=60)
def now_tz(label_tz: str) -> str:
try:
now = datetime.now(ZoneInfo(label_tz))
return now.strftime("%H:%M")
except Exception:
return "--:--"


@st.cache_data(ttl=60*15)
def fetch_weather(lat: float, lon: float):
# Open‑Meteo sem chave – previsões atuais + diária
url = "https://api.open-meteo.com/v1/forecast"
params = {
"latitude": lat,
"longitude": lon,
"current_weather": True,
"daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
"timezone": "auto",
}
r = requests.get(url, params=params, timeout=10)
r.raise_for_status()
return r.json()