import streamlit as st
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
# update or insert
mask = df["username"].astype(str).str.lower()==username.lower()
if mask.any():
df.loc[mask, ["display_name","password_hash","role","can_news","can_videos","can_birthdays","can_weather","can_rates","can_clocks","can_users","is_active"]] = [display,pwd_hash,"admin",True,True,True,True,True,True,True,True]
else:
df.loc[len(df)] = [username,display,pwd_hash,"admin",True,True,True,True,True,True,True,True]
save_users_df(df)
st.success("Admin criado. Faça login.")
st.experimental_rerun()
st.stop()


class CurrentUser:
def __init__(self, row: pd.Series):
self.username = row["username"]
self.display_name = row["display_name"]
self.role = row["role"].lower()
self.perms = {k: bool(row[k]) for k in row.index if k.startswith("can_")}
self.active = bool(row.get("is_active", True))


def can(self, key: str) -> bool:
return self.role=="admin" or self.perms.get(key, False)




def login_ui() -> CurrentUser | None:
st.session_state.setdefault("__user__", None)
if st.session_state["__user__"]:
return st.session_state["__user__"]


df = load_users_df()
with st.form("login"):
u = st.text_input("Usuário")
p = st.text_input("Senha", type="password")
ok = st.form_submit_button("Entrar")
if ok:
row = df.loc[df["username"].astype(str).str.lower()==u.lower()]
if row.empty:
st.error("Usuário não encontrado")
else:
row = row.iloc[0]
if not row.get("is_active", True):
st.error("Usuário desativado")
else:
ph = str(row.get("password_hash",""))
if ph and bcrypt.checkpw(p.encode(), ph.encode()):
user = CurrentUser(row)
st.session_state["__user__"] = user
st.experimental_rerun()
else:
st.error("Senha inválida")
return None