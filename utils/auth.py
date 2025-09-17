import streamlit as st
import pandas as pd
import bcrypt
from sheets import read_df, write_df

USERS_HEADERS = [
    "username","display_name","password_hash","role",
    "can_news","can_videos","can_birthdays","can_weather",
    "can_rates","can_clocks","can_users","is_active"
]

@st.cache_data(ttl=30)
def load_users_df() -> pd.DataFrame:
    df = read_df("users", USERS_HEADERS)
    # normaliza booleanos
    for col in [c for c in USERS_HEADERS if c.startswith("can_") or c == "is_active"]:
        df[col] = df[col].astype(str).str.upper().isin(["TRUE","1","YES","SIM","Y"])
    return df

def save_users_df(df: pd.DataFrame):
    write_df("users", USERS_HEADERS, df)
    load_users_df.clear()

def ensure_admin_bootstrap_ui():
    df = load_users_df()
    has_admin_with_hash = (
        (df["role"].astype(str).str.lower() == "admin") &
        (df["password_hash"].astype(str) != "")
    ).any()

    if not has_admin_with_hash:
        st.warning("Nenhum administrador com senha definido. Crie o admin inicial.")
        with st.form("bootstrap_admin"):
            username = st.text_input("Usuário (admin)", value="admin")
            display = st.text_input("Nome exibido", value="Admin")
            password = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Criar admin")

        if submitted:
            if not password:
                st.error("Defina uma senha.")
                st.stop()
            salt = bcrypt.gensalt()
            pwd_hash = bcrypt.hashpw(password.encode(), salt).decode()

            if df.empty:
                new = {
                    "username": username,
                    "display_name": display,
                    "password_hash": pwd_hash,
                    "role": "admin",
                    "can_news": True,
                    "can_videos": True,
                    "can_birthdays": True,
                    "can_weather": True,
                    "can_rates": True,
                    "can_clocks": True,
                    "can_users": True,
                    "is_active": True,
                }
                write_df("users", USERS_HEADERS, pd.DataFrame([new]))
            else:
                mask = df["username"].astype(str).str.lower() == username.lower()
                if mask.any():
                    df.loc[mask, [
                        "display_name","password_hash","role",
                        "can_news","can_videos","can_birthdays","can_weather",
                        "can_rates","can_clocks","can_users","is_active"
                    ]] = [display, pwd_hash, "admin", True, True, True, True, True, True, True, True]
                else:
                    df.loc[len(df)] = [username, display, pwd_hash, "admin",
                                       True, True, True, True, True, True, True, True]
                save_users_df(df)

            st.success("Admin criado. Faça login.")
            st.experimental_rerun()

        st.stop()

class CurrentUser:
    def __init__(self, row: pd.Series):
        self.username = row["username"]
        self.display_name = row["display_name"]
        self.role = str(row["role"]).lower()
        self.perms = {k: bool(row[k]) for k in row.index if k.startswith("can_")}
        self.active = bool(row.get("is_active", True))

    def can(self, key: str) -> bool:
        return self.role == "admin" or self.perms.get(key, False)

def login_ui():
    st.session_state.setdefault("__user__", None)
    if st.session_state["__user__"]:
        return st.session_state["__user__"]

    df = load_users_df()
    with st.form("login"):
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type="password")
        ok = st.form_submit_button("Entrar")

    if ok:
        row = df.loc[df["username"].astype(str).str.lower() == u.lower()]
        if row.empty:
            st.error("Usuário não encontrado")
        else:
            row = row.iloc[0]
            if not row.get("is_active", True):
                st.error("Usuário desativado")
            else:
                ph = str(row.get("password_hash", ""))
                if ph and bcrypt.checkpw(p.encode(), ph.encode()):
                    user = CurrentUser(row)
                    st.session_state["__user__"] = user
                    st.experimental_rerun()
                else:
                    st.error("Senha inválida")
    return None
