import streamlit as st
import pandas as pd
from utils.auth import login_ui, ensure_admin_bootstrap_ui
from utils.sheets import read_df, write_df

st.set_page_config(page_title="Admin – TV Corporativa", layout="wide")

ensure_admin_bootstrap_ui()
user = login_ui()
if not user:
    st.stop()

st.sidebar.success(f"Logado: {user.display_name} ({user.role})")

def bool_cols(df: pd.DataFrame, cols):
    for c in cols:
        df[c] = df[c].astype(str).str.upper().isin(["TRUE","1","YES","SIM","Y"])
    return df

tabs = []
keys = []
if user.can("can_news"):        tabs.append("Notícias");         keys.append("news")
if user.can("can_birthdays"):   tabs.append("Aniversariantes");  keys.append("birthdays")
if user.can("can_videos"):      tabs.append("Vídeos");           keys.append("videos")
if user.can("can_weather"):     tabs.append("Tempo");            keys.append("weather")
if user.can("can_clocks"):      tabs.append("Relógios");         keys.append("clocks")
if user.can("can_rates"):       tabs.append("Config / Cotações");keys.append("settings")
if user.can("can_users"):       tabs.append("Usuários");         keys.append("users")

selected = st.tabs(tabs)

SCHEMAS = {
    "news": ["id","title","description","image_url","is_active","order"],
    "birthdays": ["id","name","sector","day","month","photo_url","is_active","order"],
    "videos": ["id","title","url","duration_sec","is_active","order"],
    "weather": ["id","label","lat","lon","is_active","order"],
    "clocks": ["id","label","tz","is_active","order"],
    "settings": ["key","value"],
    "users": [
        "username","display_name","password_hash","role",
        "can_news","can_videos","can_birthdays","can_weather",
        "can_rates","can_clocks","can_users","is_active"
    ],
}

for tab, key in zip(selected, keys):
    with tab:
        headers = SCHEMAS[key]
        df = read_df(key, headers)
        st.subheader(key.capitalize())

        if key in ("news","birthdays","videos","weather","clocks"):
            df = bool_cols(df, ["is_active"]) if "is_active" in df.columns else df
            if "order" in df.columns:
                df["order"] = pd.to_numeric(df["order"], errors="coerce").fillna(0).astype(int)

            edited = st.data_editor(df, use_container_width=True, num_rows="dynamic", key=f"ed_{key}")
            if st.button("Salvar alterações", key=f"save_{key}"):
                write_df(key, headers, edited)
                st.success("Salvo.")

            with st.expander("Adicionar novo"):
                new = {h: st.text_input(h, key=f"{key}_{h}") for h in headers}
                if st.button("Adicionar", key=f"add_{key}"):
                    if key != "settings":
                        if "id" in headers and not str(new.get("id", "")).strip():
                            # gera próximo id baseado no atual
                            try:
                                current_ids = pd.to_numeric(edited.get("id", []), errors="coerce").fillna(0).astype(int)
                                new["id"] = str(int(current_ids.max()) + 1 if len(current_ids) else 1)
                            except Exception:
                                new["id"] = "1"
                    edited.loc[len(edited)] = [new.get(h, "") for h in headers]
                    write_df(key, headers, edited)
                    st.success("Adicionado.")

        elif key == "settings":
            edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
            if st.button("Salvar configurações"):
                write_df(key, headers, edited)
                st.success("Configurações salvas.")

        elif key == "users":
            st.info("Para alterar senha, gere um novo hash bcrypt (abaixo) e cole em password_hash. Admin tem todas as permissões.")
            edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
            colh1, colh2 = st.columns([1,1])
            with colh1:
                if st.button("Salvar usuários"):
                    write_df(key, headers, edited)
                    st.success("Usuários salvos.")
            with colh2:
                import bcrypt
                with st.form("hash_form"):
                    plain = st.text_input("Gerar hash bcrypt para senha:", type="password")
                    ok = st.form_submit_button("Gerar")
                if ok:
                    if not plain:
                        st.error("Informe uma senha.")
                    else:
                        salt = bcrypt.gensalt()
                        st.code(bcrypt.hashpw(plain.encode(), salt).decode())
