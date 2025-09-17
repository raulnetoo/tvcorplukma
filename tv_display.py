import re
import requests
from urllib.parse import urlparse, parse_qs
import streamlit as st
import pandas as pd
from utils.sheets import read_df
from utils.api import fetch_fx_brl, fetch_crypto_brl, fetch_weather, now_tz
from streamlit_autorefresh import st_autorefresh


st.set_page_config(page_title="TV Corporativa", layout="wide")

# === CSS ===
st.markdown(
    """
    <style>
    body { background: #0b1020; }
    .title { color: #e6f0ff; font-weight: 700; }
    .card { background: #11172a; border-radius: 16px; padding: 16px; box-shadow: 0 0 20px rgba(0,0,0,.2); }
    .text { color: #d7e3ff; }
    .muted { color: #a8b3cf; }
    .ticker { white-space: nowrap; overflow: hidden; }
    .ticker > div { display: inline-block; padding-left: 100%; animation: scroll 30s linear infinite; }
    @keyframes scroll { 0% { transform: translate(0,0);} 100% { transform: translate(-100%,0);} }
    img { border-radius: 12px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# === Config ===
SETTINGS_HEADERS = ["key", "value"]
settings_df = read_df("settings", SETTINGS_HEADERS)
def get_setting(k: str, default: int) -> int:
    if k in settings_df["key"].values:
        try:
            return int(settings_df.loc[settings_df["key"] == k, "value"].iloc[0])
        except Exception:
            return default
    return default

NEWS_MS = get_setting("news_interval_sec", 10) * 1000
BDAY_MS = get_setting("birthdays_interval_sec", 10) * 1000
VIDEO_MS = get_setting("video_interval_sec", 45) * 1000

# === Schemas ===
NEWS_HEADERS = ["id","title","description","image_url","is_active","order"]
BIRTH_HEADERS = ["id","name","sector","day","month","photo_url","is_active","order"]
VID_HEADERS = ["id","title","url","duration_sec","is_active","order"]
WEA_HEADERS = ["id","label","lat","lon","is_active","order"]
CLK_HEADERS = ["id","label","tz","is_active","order"]

# === Dados ===
news = read_df("news", NEWS_HEADERS)
news = news[news["is_active"].astype(str).str.upper().isin(["TRUE","1","YES","SIM","Y"])].sort_values("order")

birth = read_df("birthdays", BIRTH_HEADERS)
birth = birth[birth["is_active"].astype(str).str.upper().isin(["TRUE","1","YES","SIM","Y"])].sort_values("order")

vids = read_df("videos", VID_HEADERS)
vids = vids[vids["is_active"].astype(str).str.upper().isin(["TRUE","1","YES","SIM","Y"])].sort_values("order")

locs = read_df("weather", WEA_HEADERS)
locs = locs[locs["is_active"].astype(str).str.upper().isin(["TRUE","1","YES","SIM","Y"])].sort_values("order")

clocks = read_df("clocks", CLK_HEADERS)
clocks = clocks[clocks["is_active"].astype(str).str.upper().isin(["TRUE","1","YES","SIM","Y"])].sort_values("order")

# === Autorefresh / Índices ===
# 1) Ler query params com a nova API
params = st.query_params  # dict-like
news_count = int(params.get("nc", "0"))
bday_count = int(params.get("bc", "0"))
video_count = int(params.get("vc", "0"))

# 2) Incrementar contadores (se houver itens)
nc = news_count + 1 if not news.empty else 0
bc = bday_count + 1 if not birth.empty else 0
vc = video_count + 1 if not vids.empty else 0

# 3) Gravar de volta nos query params (nova API)
st.query_params.update({"nc": str(nc), "bc": str(bc), "vc": str(vc)})

# 4) Selecionar índices atuais
news_idx = (nc - 1) % len(news) if len(news) else 0
bday_idx = (bc - 1) % len(birth) if len(birth) else 0
vid_idx  = (vc - 1) % len(vids) if len(vids) else 0

# 5) Auto-refresh
# OBS: abaixo eu mantive 3 timers independentes como você tinha.
# Em páginas Streamlit, múltiplos autorefresh vão provocar recarregamentos em tempos diferentes,
# o que na prática significa que a página recarrega no menor intervalo configurado.
# Se quiser respeitar cadências diferentes por seção, recomendo depois migrar para UM único
# st_autorefresh e controlar a rotação via timestamps em st.session_state.
st_autorefresh(interval=NEWS_MS, key="news_tick")
st_autorefresh(interval=BDAY_MS, key="bday_tick")
st_autorefresh(interval=VIDEO_MS, key="video_tick")

# ==== Helpers de vídeo (YouTube / Google Drive / Link direto) ====

YOUTUBE_PATTERNS = [
    r"(?:v=|\/embed\/|youtu\.be\/)([A-Za-z0-9_-]{11})",
]

def extract_youtube_id(url: str) -> str | None:
    u = str(url or "").strip()
    if not u:
        return None
    # tenta regex
    for pat in YOUTUBE_PATTERNS:
        m = re.search(pat, u)
        if m:
            return m.group(1)
    # tenta query param v=
    try:
        q = parse_qs(urlparse(u).query)
        if "v" in q and len(q["v"]) > 0 and len(q["v"][0]) == 11:
            return q["v"][0]
    except Exception:
        pass
    return None

def extract_drive_id(url: str) -> str | None:
    """Suporta formatos:
       https://drive.google.com/file/d/FILE_ID/view?usp=sharing
       https://drive.google.com/uc?export=download&id=FILE_ID
    """
    u = str(url or "").strip()
    if not u:
        return None
    m = re.search(r"/file/d/([A-Za-z0-9_-]+)/", u)
    if m:
        return m.group(1)
    # tenta por query id=
    try:
        q = parse_qs(urlparse(u).query)
        if "id" in q and len(q["id"]) > 0:
            return q["id"][0]
    except Exception:
        pass
    return None

def render_video(url: str, *, height: int = 380):
    """Renderiza vídeo com fallback inteligente."""
    u = str(url or "").strip()
    if not u:
        st.warning("URL de vídeo vazia.")
        return

    # 1) YouTube -> embed <iframe>
    if "youtube.com" in u or "youtu.be" in u:
        vid = extract_youtube_id(u)
        if vid:
            st.markdown(
                f"""
                <div style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;border-radius:12px;">
                  <iframe
                    src="https://www.youtube.com/embed/{vid}?autoplay=1&mute=1&controls=1&rel=0"
                    frameborder="0"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                    allowfullscreen
                    style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;border-radius:12px;">
                  </iframe>
                </div>
                """,
                unsafe_allow_html=True,
            )
            return

    # 2) Google Drive -> /preview <iframe>
    if "drive.google.com" in u:
        fid = extract_drive_id(u)
        if fid:
            st.markdown(
                f"""
                <div style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;border-radius:12px;">
                  <iframe
                    src="https://drive.google.com/file/d/{fid}/preview"
                    frameborder="0"
                    allow="autoplay"
                    allowfullscreen
                    style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;border-radius:12px;">
                  </iframe>
                </div>
                """,
                unsafe_allow_html=True,
            )
            return

    # 3) Link direto (mp4/webm/ogg) -> tenta HEAD e usa st.video
    try:
        h = requests.head(u, allow_redirects=True, timeout=8)
        ct = (h.headers.get("content-type") or "").lower()
    except Exception:
        ct = ""

    if any(u.lower().endswith(ext) for ext in (".mp4", ".webm", ".ogg")) or "video" in ct:
        # st.video aceita URL direta pública
        try:
            st.video(u)
            return
        except Exception:
            pass  # cai pro fallback

    # 4) Fallback genérico em iframe (alguns players/CDNs funcionam)
    st.markdown(
        f"""
        <div style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;border-radius:12px;">
          <iframe
            src="{u}"
            frameborder="0"
            allow="autoplay; encrypted-media"
            allowfullscreen
            style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;border-radius:12px;">
          </iframe>
        </div>
        """,
        unsafe_allow_html=True,
    )

# === GRID ===
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("<h2 class='title'>Notícias</h2>", unsafe_allow_html=True)
    if news.empty:
        st.info("Cadastre notícias no admin.")
    else:
        row = news.iloc[news_idx]
        with st.container():
            st.markdown(
                f"<div class='text'><h3>{row['title']}</h3><p class='muted'>{row['description']}</p></div>",
                unsafe_allow_html=True
            )
            if str(row["image_url"]).strip():
                st.image(row["image_url"], use_container_width=True)

    st.markdown("<h2 class='title' style='margin-top:24px'>Vídeos institucionais</h2>", unsafe_allow_html=True)
    if vids.empty:
        st.info("Cadastre vídeos no admin.")
    else:
        v = vids.iloc[vid_idx]
        render_video(v["url"])

with col2:
    st.markdown("<h2 class='title'>Aniversariantes do mês</h2>", unsafe_allow_html=True)
    if birth.empty:
        st.info("Cadastre aniversariantes no admin.")
    else:
        b = birth.iloc[bday_idx]
        with st.container():
            st.balloons()  # efeito festivo
            if str(b["photo_url"]).strip():
                st.image(b["photo_url"], use_container_width=True)
            # dia/mês como inteiros (se possível)
            try:
                dia = int(b["day"])
            except Exception:
                dia = b["day"]
            try:
                mes = int(b["month"])
            except Exception:
                mes = b["month"]
            st.markdown(
                f"<div class='text'><h3>{b['name']}</h3>"
                f"<p class='muted'>{b['sector']} • {dia}/{mes}</p></div>",
                unsafe_allow_html=True
            )

    st.markdown("<h2 class='title' style='margin-top:24px'>Relógios</h2>", unsafe_allow_html=True)
    if clocks.empty:
        st.info("Defina relógios no admin.")
    else:
        c1, c2 = st.columns(2)
        half = (len(clocks) + 1) // 2
        for i, row in enumerate(clocks.itertuples(index=False)):
            target = c1 if i < half else c2
            with target:
                st.markdown(
                    f"<div class='card'><div class='text'><h4>{row.label}</h4>"
                    f"<div class='title' style='font-size:42px'>{now_tz(row.tz)}</div></div></div>",
                    unsafe_allow_html=True
                )

# === Tempo + Cotações ===
st.markdown("<h2 class='title' style='margin-top:16px'>Tempo e Cotações</h2>", unsafe_allow_html=True)

# Tempo (ticker rolante)
if locs.empty:
    st.info("Cadastre locais do tempo no admin.")
else:
    parts = []
    for loc in locs.itertuples(index=False):
        try:
            js = fetch_weather(float(loc.lat), float(loc.lon))
            cur = js.get("current_weather", {})
            daily = js.get("daily", {})
            t = cur.get("temperature")
            tmax = daily.get("temperature_2m_max", [None])[0]
            tmin = daily.get("temperature_2m_min", [None])[0]
            parts.append(f"{loc.label}: {t}°C (min {tmin}°C / max {tmax}°C)")
        except Exception:
            parts.append(f"{loc.label}: --°C")
    ticker = "  •  ".join(parts)
    st.markdown(f"<div class='card ticker'><div>{ticker}</div></div>", unsafe_allow_html=True)

# Cotações
fx = fetch_fx_brl()
cc = fetch_crypto_brl()

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Dólar (USD → BRL)", f"R$ {fx['USD']:.2f}" if fx.get("USD") else "--")
with c2:
    st.metric("Euro (EUR → BRL)", f"R$ {fx['EUR']:.2f}" if fx.get("EUR") else "--")
with c3:
    st.metric("Bitcoin (BTC)", f"R$ {cc['BTC']:,.0f}".replace(",", ".") if cc.get("BTC") else "--")
with c4:
    st.metric("Ethereum (ETH)", f"R$ {cc['ETH']:,.0f}".replace(",", ".") if cc.get("ETH") else "--")
