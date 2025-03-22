"""
Frontend Streamlit per l'analisi AI di database PostgreSQL attraverso tunnel SSH.
Include sistema di login e gestione configurazioni tramite file .env
"""
import os
import json
import pandas as pd   # type: ignore
import streamlit as st   # type: ignore
import requests   # type: ignore
from io import BytesIO
from dotenv import load_dotenv   # type: ignore


# Carica variabili d'ambiente
load_dotenv()


# Costanti dell'applicazione
APP_TITLE = "Analisi AI del Database PostgreSQL con Tunnel SSH"
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
CREDENTIALS_FILE = os.getenv("CREDENTIALS_FILE", "/app/credentials.json")


# Domande predefinite
DOMANDE_SUGGERITE = [
    "Mostrami il totale delle vendite per categoria",
    "Qual è stato il prodotto più venduto negli ultimi 6 mesi?",
    "Qual è la media dei prezzi unitari per categoria?",
    "Quanti articoli sono stati venduti per ciascuna categoria?",
    "Mostrami l'andamento delle vendite negli ultimi 12 mesi"
]


class AuthManager:
    """Gestisce l'autenticazione dell'utente."""

    def __init__(self):
        """Inizializza il gestore dell'autenticazione con le credenziali dal file .env."""
        self.admin_username = os.getenv("ADMIN_USERNAME")
        self.admin_password = os.getenv("ADMIN_PASSWORD")

        if not self.admin_username or not self.admin_password:
            st.error("Credenziali di amministratore non configurate nel file .env")

    def login_page(self):
        """Gestisce la pagina di login e verifica le credenziali."""
        st.title("Login")

        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit_button = st.form_submit_button("Accedi")

            if submit_button:
                if username == self.admin_username and password == self.admin_password:
                    st.session_state.logged_in = True
                    st.success("Login effettuato con successo!")
                    st.experimental_rerun()
                else:
                    st.error("Username o password non validi")

    def check_login(self):
        """Verifica se l'utente è loggato."""
        if "logged_in" not in st.session_state:
            st.session_state.logged_in = False

        return st.session_state.logged_in

    def logout(self):
        """Effettua il logout dell'utente."""
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.experimental_rerun()


class CredentialsManager:
    """Gestisce il caricamento e il salvataggio delle credenziali."""

    def __init__(self, credentials_file):
        """Inizializza il gestore delle credenziali."""
        self.credentials_file = credentials_file
        self.credentials = self.load_credentials()

    def load_credentials(self):
        """Carica le credenziali salvate dal file."""
        if os.path.exists(self.credentials_file):
            with open(self.credentials_file, "r") as file:
                return json.load(file)
        return {}

    def save_credentials(self):
        """Salva le credenziali nel file."""
        # Assicuriamoci che la directory esista
        os.makedirs(os.path.dirname(self.credentials_file), exist_ok=True)

        with open(self.credentials_file, "w") as file:
            json.dump(self.credentials, file)

    def get_ssh_config(self):
        """Restituisce la configurazione SSH."""
        return {
            "ssh_host": self.credentials.get("ssh_host", ""),
            "ssh_user": self.credentials.get("ssh_user", ""),
            "ssh_key": self.credentials.get("ssh_key", "")
        }

    def get_db_config(self):
        """Restituisce la configurazione del database."""
        return {
            "host": self.credentials.get("db_host", ""),
            "port": self.credentials.get("db_port", ""),
            "user": self.credentials.get("db_user", ""),
            "password": self.credentials.get("db_password", ""),
            "database": self.credentials.get("db_name", "")
        }


class UserInterface:
    """Gestisce l'interfaccia utente dell'applicazione."""

    def __init__(self, credentials_manager):
        """Inizializza l'interfaccia utente."""
        self.credentials_manager = credentials_manager

    def render_sidebar(self):
        """Visualizza la sidebar con le impostazioni."""
        st.sidebar.header("Configurazione OpenAI")
        self.credentials_manager.credentials["openai_api_key"] = st.sidebar.text_input(
            "Chiave OpenAI",
            type="password",
            value=self.credentials_manager.credentials.get("openai_api_key", "")
        )

        st.sidebar.header("Configurazione SSH")
        self.credentials_manager.credentials["ssh_host"] = st.sidebar.text_input(
            "IP Server SSH",
            value=self.credentials_manager.credentials.get("ssh_host", "192.168.1.100")
        )
        self.credentials_manager.credentials["ssh_user"] = st.sidebar.text_input(
            "Utente SSH",
            value=self.credentials_manager.credentials.get("ssh_user", "ubuntu")
        )
        self.credentials_manager.credentials["ssh_key"] = st.sidebar.text_area(
            "Chiave Privata SSH",
            value=self.credentials_manager.credentials.get("ssh_key", "")
        )

        st.sidebar.header("Configurazione Database PostgreSQL")
        self.credentials_manager.credentials["db_host"] = st.sidebar.text_input(
            "Host PostgreSQL",
            value=self.credentials_manager.credentials.get("db_host", "127.0.0.1")
        )
        self.credentials_manager.credentials["db_port"] = st.sidebar.text_input(
            "Porta PostgreSQL",
            value=self.credentials_manager.credentials.get("db_port", "5432")
        )
        self.credentials_manager.credentials["db_user"] = st.sidebar.text_input(
            "Utente Database",
            value=self.credentials_manager.credentials.get("db_user", "postgres")
        )
        self.credentials_manager.credentials["db_password"] = st.sidebar.text_input(
            "Password Database",
            type="password",
            value=self.credentials_manager.credentials.get("db_password", "")
        )
        self.credentials_manager.credentials["db_name"] = st.sidebar.text_input(
            "Nome Database",
            value=self.credentials_manager.credentials.get("db_name", "mio_database")
        )

        if st.sidebar.button("Salva credenziali"):
            self.credentials_manager.save_credentials()
            st.sidebar.success("Credenziali salvate con successo!")

    def render_main_interface(self):
        """Visualizza l'interfaccia principale dell'applicazione."""
        st.title(APP_TITLE)

        # Selettore domande
        domanda_selezionata = st.selectbox(
            "Seleziona una domanda",
            ["Scrivi la tua domanda..."] + DOMANDE_SUGGERITE
        )
        domanda_input = st.text_input("Oppure scrivi una domanda libera:")

        # Checkbox per forzare la rigenerazione della query senza cache
        force_no_cache = st.checkbox("Forza rigenerazione query SQL (ignora cache)")

        # Inizializzazione dello stato dei pulsanti
        if "cerca_clicked" not in st.session_state:
            st.session_state.cerca_clicked = False
        if "refresh_clicked" not in st.session_state:
            st.session_state.refresh_clicked = False

        # Pulsanti per le azioni
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("🔍 Cerca", use_container_width=True):
                st.session_state.cerca_clicked = True
        with col2:
            if st.button("🔄 Riscansiona Database", use_container_width=True):
                st.session_state.refresh_clicked = True

        return {
            "domanda": domanda_input if domanda_input else domanda_selezionata,
            "force_no_cache": force_no_cache
        }


class BackendClient:
    """Gestisce le chiamate API al backend."""

    def __init__(self, backend_url):
        """Inizializza il client backend."""
        self.backend_url = backend_url

    def execute_query(self, domanda, openai_api_key, ssh_config, db_config, force_no_cache=False):
        """Esegue una query al backend."""
        response = requests.post(
            f"{self.backend_url}/query",
            json={
                "domanda": domanda,
                "openai_api_key": openai_api_key,
                "ssh_config": ssh_config,
                "db_config": db_config,
                "force_no_cache": force_no_cache
            }
        )
        return response

    def refresh_schema(self, ssh_config, db_config):
        """Aggiorna lo schema del database."""
        response = requests.post(
            f"{self.backend_url}/refresh_schema",
            json={
                "ssh_config": ssh_config,
                "db_config": db_config
            }
        )
        return response


class ResultVisualizer:
    """Gestisce la visualizzazione dei risultati dell'analisi."""

    @staticmethod
    def display_results(data):
        """Visualizza i risultati dell'analisi."""
        st.success("✅ Analisi completata!")

        # Mostra descrizione AI
        st.subheader("📖 Interpretazione AI:")
        st.write(f"analisi: {data['descrizione']}")
        st.write(f"query: {data['query_sql']}")

        # Notifica sulla cache
        if data.get("cache_used", False):
            st.success("✅ Risultato generazione SQL preso dalla cache!")
        else:
            st.warning("⚠️ La query è stata rigenerata senza cache.")

        # Visualizza i dati in tabella
        df = pd.DataFrame(data["dati"])
        st.subheader("📋 Dati Analizzati:")
        st.dataframe(df)

        # Mostra i grafici
        if "grafici" in data and data["grafici"]:
            st.subheader("📊 Grafici Generati dall'AI")
            st.image(data["grafici"], caption="Grafico Generato", use_column_width=True)

        # Scarica il file Excel
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


def main():
    """Funzione principale dell'applicazione."""
    # Inizializzazione dei gestori
    auth_manager = AuthManager()
    credentials_manager = CredentialsManager(CREDENTIALS_FILE)
    ui = UserInterface(credentials_manager)
    backend_client = BackendClient(BACKEND_URL)

    # Verifica del login
    if not auth_manager.check_login():
        auth_manager.login_page()
        return

    # Logout nella sidebar
    auth_manager.logout()

    # Rendering della sidebar
    ui.render_sidebar()

    # Rendering dell'interfaccia principale
    ui_data = ui.render_main_interface()

    # Gestione dell'azione "Cerca"
    if st.session_state.cerca_clicked:
        st.session_state.cerca_clicked = False

        domanda = ui_data["domanda"]
        if domanda:
            st.info("Analisi in corso...")

            response = backend_client.execute_query(
                domanda=domanda,
                openai_api_key=credentials_manager.credentials["openai_api_key"],
                ssh_config=credentials_manager.get_ssh_config(),
                db_config=credentials_manager.get_db_config(),
                force_no_cache=ui_data["force_no_cache"]
            )

            if response.status_code == 200:
                data = response.json()
                if "errore" in data:
                    st.error(data["errore"])
                else:
                    ResultVisualizer.display_results(data)
            else:
                st.error("❌ Errore nell'elaborazione della richiesta.")

    # Gestione dell'azione "Riscansiona Database"
    if st.session_state.refresh_clicked:
        st.session_state.refresh_clicked = False

        st.info("Avvio riscansione del database...")
        response = backend_client.refresh_schema(
            ssh_config=credentials_manager.get_ssh_config(),
            db_config=credentials_manager.get_db_config()
        )

        if response.status_code == 200:
            st.success("✅ Struttura del database aggiornata!")
        else:
            st.error("❌ Errore durante la riscansione del database.")


# Punto di ingresso dell'applicazione
if __name__ == "__main__":
    main()
