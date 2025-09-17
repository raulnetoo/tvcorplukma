import streamlit as st
v = vids.iloc[vid_idx]
st.video(v["url"]) # rotaciona pelo autorefresh de VIDEO_MS


with col2:
st.markdown("<h2 class='title'>Aniversariantes do mês</h2>", unsafe_allow_html=True)
if birth.empty:
st.info("Cadastre aniversariantes no admin.")
else:
b = birth.iloc[bday_idx]
with st.container():
st.balloons() # efeito festivo
if str(b["photo_url"]).strip():
st.image(b["photo_url"], use_container_width=True)
st.markdown(f"<div class='text'><h3>{b['name']}</h3><p class='muted'>{b['sector']} • {int(b['day'])}/{int(b['month'])}</p></div>", unsafe_allow_html=True)


st.markdown("<h2 class='title' style='margin-top:24px'>Relógios</h2>", unsafe_allow_html=True)
if clocks.empty:
st.info("Defina relógios no admin.")
else:
c1, c2 = st.columns(2)
half = (len(clocks)+1)//2
for i, row in enumerate(clocks.itertuples(index=False)):
target = c1 if i < half else c2
with target:
st.markdown(f"<div class='card'><div class='text'><h4>{row.label}</h4><div class='title' style='font-size:42px'>{now_tz(row.tz)}</div></div></div>", unsafe_allow_html=True)


# Linha completa para Clima + Cotações
st.markdown("<h2 class='title' style='margin-top:16px'>Tempo e Cotações</h2>", unsafe_allow_html=True)


# Tempo (ticker)
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
ticker = " • ".join(parts)
st.markdown(f"<div class='card ticker'><div>{ticker}</div></div>", unsafe_allow_html=True)


# Cotações
fx = fetch_fx_brl()
cc = fetch_crypto_brl()


c1, c2, c3, c4 = st.columns(4)
with c1:
st.metric("Dólar (USD → BRL)", fx.get("USD") and f"R$ {fx['USD']:.2f}" or "--")
with c2:
st.metric("Euro (EUR → BRL)", fx.get("EUR") and f"R$ {fx['EUR']:.2f}" or "--")
with c3:
st.metric("Bitcoin (BTC)", cc.get("BTC") and f"R$ {cc['BTC']:,.0f}".replace(",",".") or "--")
with c4:
st.metric("Ethereum (ETH)", cc.get("ETH") and f"R$ {cc['ETH']:,.0f}".replace(",",".") or "--")