import streamlit as st  # type: ignore
import requests  # type: ignore
import json
import os
import pandas as pd  # type: ignore
from io import BytesIO

CREDENTIALS_FILE = "/app/credentials.json"


# Funzione per caricare le credenziali salvate
def load_credentials():
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "r") as file:
            return json.load(file)
    return {}


# Funzione per salvare le credenziali
def save_credentials(credentials):
    with open(CREDENTIALS_FILE, "w") as file:
        json.dump(credentials, file)


# **Carica le credenziali salvate**
credentials = load_credentials()


st.title("Analisi AI del Database PostgreSQL con Tunnel SSH")

# **Configurazione OpenAI**
st.sidebar.header("Configurazione OpenAI")
credentials["openai_api_key"] = st.sidebar.text_input(
    "Chiave OpenAI", type="password", value=credentials.get("openai_api_key", "")
)

# **Configurazione SSH**
st.sidebar.header("Configurazione SSH")
credentials["ssh_host"] = st.sidebar.text_input("IP Server SSH", value=credentials.get("ssh_host", "192.168.1.100"))
credentials["ssh_user"] = st.sidebar.text_input("Utente SSH", value=credentials.get("ssh_user", "ubuntu"))
credentials["ssh_key"] = st.sidebar.text_area("Chiave Privata SSH", value=credentials.get("ssh_key", ""))

# **Configurazione Database**
st.sidebar.header("Configurazione Database PostgreSQL")
credentials["db_host"] = st.sidebar.text_input("Host PostgreSQL", value=credentials.get("db_host", "127.0.0.1"))
credentials["db_port"] = st.sidebar.text_input("Porta PostgreSQL", value=credentials.get("db_port", "5432"))
credentials["db_user"] = st.sidebar.text_input("Utente Database", value=credentials.get("db_user", "postgres"))
credentials["db_password"] = st.sidebar.text_input("Password Database", type="password", value=credentials.get("db_password", ""))
credentials["db_name"] = st.sidebar.text_input("Nome Database", value=credentials.get("db_name", "mio_database"))


def get_ssh_config():
    return {
        "ssh_host": credentials["ssh_host"],
        "ssh_user": credentials["ssh_user"],
        "ssh_key": credentials["ssh_key"]
    }


def get_db_config():
    return {
        "host": credentials["db_host"],
        "port": credentials["db_port"],
        "user": credentials["db_user"],
        "password": credentials["db_password"],
        "database": credentials["db_name"]
    }


# **Salva le credenziali quando cambia un valore**
if st.sidebar.button("Salva credenziali"):
    save_credentials(credentials)
    st.sidebar.success("Credenziali salvate con successo!")

# **Selezione domanda**
DOMANDE_SUGGERITE = [
    "Mostrami il totale delle vendite per categoria",
    "Qual è stato il prodotto più venduto negli ultimi 6 mesi?",
    "Qual è la media dei prezzi unitari per categoria?",
    "Quanti articoli sono stati venduti per ciascuna categoria?",
    "Mostrami l’andamento delle vendite negli ultimi 12 mesi"
]

# **Configurazione API**
BACKEND_URL = "http://backend:8000"

domanda_selezionata = st.selectbox("Seleziona una domanda", ["Scrivi la tua domanda..."] + DOMANDE_SUGGERITE)
domanda_input = st.text_input("Oppure scrivi una domanda libera:")

# ✅ Checkbox per forzare la rigenerazione della query senza cache
force_no_cache = st.checkbox("Forza rigenerazione query SQL (ignora cache)")

# Inizializziamo lo stato dei pulsanti (se non esiste)
if "cerca_clicked" not in st.session_state:
    st.session_state.cerca_clicked = False

if "refresh_clicked" not in st.session_state:
    st.session_state.refresh_clicked = False

# Creiamo due colonne per i pulsanti
col1, col2 = st.columns([1, 1])


# Pulsante "Cerca" nella prima colonna
with col1:
    if st.button("🔍 Cerca", use_container_width=True):
        st.session_state.cerca_clicked = True  # ✅ Settiamo lo stato su True

with col2:
    if st.button("🔄 Riscansiona Database", use_container_width=True):
        st.session_state.refresh_clicked = True  # ✅ Settiamo lo stato su True

# Esegui "Cerca"
if st.session_state.cerca_clicked:
    st.session_state.cerca_clicked = False  # ✅ Resettiamo lo stato

    domanda = domanda_input if domanda_input else domanda_selezionata
    if domanda:
        st.info("Analisi in corso...")

        response = requests.post(f"{BACKEND_URL}/query", json={
            "domanda": domanda,
            "openai_api_key": credentials["openai_api_key"],
            "ssh_config": get_ssh_config(),
            "db_config": get_db_config()
        })

        if response.status_code == 200:
            data = response.json()
            if "errore" in data:
                st.error(data["errore"])
            else:
                st.success("✅ Analisi completata!")

                # **1️⃣ Mostra descrizione AI**
                st.subheader("📖 Interpretazione AI:")
                st.write(f"analisi: {data['descrizione']}")
                st.write(f"query: {data['query_sql']}")

                cache_used = data["cache_used"]

                # ✅ Notifica all'utente se la cache è stata usata
                if cache_used:
                    st.success("✅ Risultato generazione SQL preso dalla cache!")
                else:
                    st.warning("⚠️ La query è stata rigenerata senza cache.")

                # **2️⃣ Visualizza i dati in tabella**
                df = pd.DataFrame(data["dati"])
                st.subheader("📋 Dati Analizzati:")
                st.dataframe(df)

                # **3️⃣ Mostra i grafici**
                if "grafici" in data and data["grafici"]:
                    st.subheader("📊 Grafici Generati dall'AI")
                    st.image(data["grafici"], caption="Grafico Generato", use_column_width=True)

                # **4️⃣ Scarica il file Excel**
                if not df.empty:
                    st.subheader("📥 Scarica i Dati in Excel")
                    output = BytesIO()
                    df.to_excel(output, index=False, engine='xlsxwriter')
                    output.seek(0)
                    st.download_button(
                        label="📥 Scarica Excel",
                        data=output,
                        file_name="analisi.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
        else:
            st.error("❌ Errore nell'elaborazione della richiesta.")

# esegui "Riscansiona Database"
if st.session_state.refresh_clicked:
    st.session_state.refresh_clicked = False  # ✅ Resettiamo lo stato

    st.info("Avvio riscansione del database...")
    response = requests.post(f"{BACKEND_URL}/refresh_schema", json={
        "ssh_config": get_ssh_config(),
        "db_config": get_db_config()
    })

    if response.status_code == 200:
        st.success("✅ Struttura del database aggiornata!")
    else:
        st.error("❌ Errore durante la riscansione del database.")
