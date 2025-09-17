import streamlit as st
# Mapas de schema
SCHEMAS = {
"news": ["id","title","description","image_url","is_active","order"],
"birthdays": ["id","name","sector","day","month","photo_url","is_active","order"],
"videos": ["id","title","url","duration_sec","is_active","order"],
"weather": ["id","label","lat","lon","is_active","order"],
"clocks": ["id","label","tz","is_active","order"],
"settings": ["key","value"],
"users": [
"username","display_name","password_hash","role","can_news","can_videos","can_birthdays","can_weather","can_rates","can_clocks","can_users","is_active"
],
}


for tab, key in zip(selected, keys):
with tab:
headers = SCHEMAS[key]
df = read_df(key, headers)
st.subheader(key.capitalize())


if key in ("news","birthdays","videos","weather","clocks"):
# Normaliza
df = bool_cols(df, ["is_active"]) if "is_active" in df.columns else df
if "order" in df.columns:
df["order"] = pd.to_numeric(df["order"], errors="coerce").fillna(0).astype(int)
edited = st.data_editor(df, use_container_width=True, num_rows="dynamic", key=f"ed_{key}")
if st.button("Salvar alterações", key=f"save_{key}"):
write_df(key, headers, edited)
st.success("Salvo.")


# Formulário rápido de inclusão
with st.expander("Adicionar novo"):
new = {h: st.text_input(h, key=f"{key}_{h}") for h in headers}
if st.button("Adicionar", key=f"add_{key}"):
# Append linha
if key != "settings":
# tenta id auto se vazio
if not new.get("id") and "id" in headers:
new["id"] = str(max([int(x) for x in edited.get("id",[]).astype(str).str.extract(r"(\d+)")[0].fillna(0)] + [0]) + 1)
edited.loc[len(edited)] = [new.get(h, "") for h in headers]
write_df(key, headers, edited)
st.success("Adicionado.")


elif key == "settings":
edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
if st.button("Salvar configurações"):
write_df(key, headers, edited)
st.success("Configurações salvas.")


elif key == "users":
st.info("Para alterar senha, cole um novo hash bcrypt em password_hash (use o gerador abaixo). Admin tem todas as permissões.")
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