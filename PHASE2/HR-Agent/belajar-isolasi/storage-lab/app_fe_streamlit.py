import os
import requests
import streamlit as st

st.set_page_config(
    page_title="HR Assistant - Eksperimen Frontend",
    page_icon="😌",
    layout="centered"
)

# Konfigurasi Backend API
st.sidebar.title("⚙️ Pengaturan Koneksi")
api_base_url = st.sidebar.text_input("URL Backend FastAPI", value="http://localhost:8002")

# Pilihan Persona (simulasi Login/Token)
PERSONAS = {
    "Alya Pratama (Employee)": "token-alya",
    "Bima Santoso (Employee)": "token-bima",
    "Monitoring Admin (Admin)": "token-admin",
}

selected_persona_name = st.sidebar.selectbox("Pilih Persona Karyawan:", list(PERSONAS.keys()))
active_token = PERSONAS[selected_persona_name]

# Reset chat jika berganti persona
if "current_persona" not in st.session_state:
    st.session_state.current_persona = selected_persona_name
    st.session_state.messages = []

if st.session_state.current_persona != selected_persona_name:
    st.session_state.current_persona = selected_persona_name
    st.session_state.messages = []
    st.sidebar.info("Persona diganti, riwayat chat di-reset.")

# Tombol Bersihkan Chat
if st.sidebar.button("🗑️ Bersihkan Obrolan"):
    st.session_state.messages = []
    st.rerun()

# Cek status kesehatan backend (opsional)
with st.sidebar.expander("Status Server"):
    st.write(f"**Token:** `{active_token}`")
    if st.button("Cek Koneksi Backend"):
        try:
            res = requests.get(f"{api_base_url}/openapi.json", timeout=3)
            if res.status_code == 200:
                st.success("✅ Backend FastAPI terhubung!")
            else:
                st.warning(f"⚠️ Respon server: {res.status_code}")
        except Exception as e:
            st.error(f"❌ Gagal koneksi: {e}")

# Header Utama
st.title("🎰 AI asisten ADMIN General 👾")
st.caption(f"Sedang berinteraksi sebagai: **{selected_persona_name}**")

# Tampilkan riwayat percakapan
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "meta" in msg:
            st.caption(f"ID Karyawan: `{msg['meta']}`")

# Input pengguna
if user_prompt := st.chat_input("Tulis pertanyaan Anda seputar HR atau cuti..."):
    # Tampilkan pesan user di UI
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    # Kirim ke backend FastAPI
    with st.chat_message("assistant"):
        with st.spinner("Menghubungi FastAPI & AI..."):
            try:
                headers = {
                    "Authorization": f"Bearer {active_token}",
                    "Content-Type": "application/json"
                }
                payload = {"message": user_prompt}
                
                response = requests.post(
                    f"{api_base_url}/api/v1/chat",
                    headers=headers,
                    json=payload,
                    timeout=60
                )

                if response.status_code == 200:
                    data = response.json()
                    answer = data.get("answer", "Tidak ada jawaban.")
                    emp_id = data.get("employee_id", "-")

                    st.markdown(answer)
                    st.caption(f"ID Karyawan: `{emp_id}`")

                    # Simpan ke riwayat session
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "meta": emp_id
                    })
                else:
                    error_msg = f"Error {response.status_code}: {response.text}"
                    st.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"⚠️ {error_msg}"
                    })

            except requests.exceptions.ConnectionError:
                err = "Tidak dapat terhubung ke FastAPI. Pastikan Uvicorn port 8002 sedang aktif!"
                st.error(err)
                st.session_state.messages.append({"role": "assistant", "content": f"❌ {err}"})
            except Exception as e:
                err = f"Terjadi kesalahan: {e}"
                st.error(err)
                st.session_state.messages.append({"role": "assistant", "content": f"❌ {err}"})
