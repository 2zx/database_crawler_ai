"""
Frontend Streamlit per l'analisi AI di database PostgreSQL attraverso tunnel SSH.
Include sistema di login, gestione configurazioni tramite file .env,
sistema di hint per l'interpretazione dei dati e supporto per diversi provider LLM.
"""
import os
import json
import time
import pandas as pd   # type: ignore
import streamlit as st   # type: ignore
import requests   # type: ignore
from io import BytesIO
from dotenv import load_dotenv   # type: ignore
import logging


# Configura il logging per vedere gli errori nel container
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carica variabili d'ambiente
load_dotenv()

# Costanti dell'applicazione
APP_TITLE = "L’AI che lavora per la tua lavanderia industriale"
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
CREDENTIALS_FILE = os.getenv("CREDENTIALS_FILE", "/app/credentials.json")

# Domande predefinite
DOMANDE_SUGGERITE = {
    "montanari": [
        "Qual'è l'impianto di confezionamento che produce più quintail? fai una comparazione tra quelli presenti valutando le medie produttive degil ultimi 6 mesi",
        "Come si distribuiscono i prodotti per impianto di confezionamento?",
        "Qual'è la media oraria di produzione per impianto di confezionamento?",
        "Fai un'analisi sui picchi orari gionnalieri di produzione per giorno della settimana ed impianto di confezionamento",
        "Qual'è la media pacchi minuto di produzione per impianto di confezionamento degli ultimi 12 mesi?"
    ],
    "jit40": [
        "Mostrami l'andamento del fatturato dell'ultimo anno per categoria",
        "Qual è stato il prodotto più consegnato negli ultimi 6 mesi?",
        "Qual è la media dei prezzi unitari per categoria?",
        "Qual'è, in quintali, il bollettato medio settimanale per ciascuna categoria?",
    ]
}


# Configurazione dei provider LLM
LLM_PROVIDERS = {
    "openai": {"name": "OpenAI", "api_key_name": "openai_api_key", "requires_secret": False},
    "claude": {"name": "Anthropic Claude", "api_key_name": "claude_api_key", "requires_secret": False},
    "deepseek": {"name": "DeepSeek", "api_key_name": "deepseek_api_key", "requires_secret": False},
    "ernie": {"name": "Baidu ERNIE", "api_key_name": "ernie_api_key", "requires_secret": True,
              "secret_key_name": "ernie_secret_key"}
}

# temp
st.session_state.logged_in = True

st.set_page_config(
    page_title="JIT40 Laundry Bot",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': APP_TITLE
    }
)


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
                    st.rerun()
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
            st.rerun()


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
            "database": self.credentials.get("db_name", ""),
            "db_type": self.credentials.get("db_type", "postgresql"),
            "hint_category": self.credentials.get("hint_category", "generale")  # Aggiunto per la categoria hint
        }

    def get_llm_config(self):
        """Restituisce la configurazione del LLM selezionato."""
        provider = self.credentials.get("llm_provider", "openai")
        config = {
            "provider": provider,
            "api_key": self.credentials.get(LLM_PROVIDERS[provider]["api_key_name"], ""),
            "model": self.credentials.get(f"{provider}_model", "")
        }

        # Aggiungi secret_key per Baidu ERNIE se necessario
        if provider == "ernie" and LLM_PROVIDERS[provider]["requires_secret"]:
            config["secret_key"] = self.credentials.get(LLM_PROVIDERS[provider]["secret_key_name"], "")

        return config


class LLMManager:
    """Gestisce le configurazioni e le operazioni relative ai LLM."""

    def __init__(self, backend_url):
        """Inizializza il gestore LLM."""
        self.backend_url = backend_url
        self.available_models = self.fetch_available_models()

    def fetch_available_models(self):
        """Recupera l'elenco dei modelli disponibili dal backend."""
        try:
            response = requests.get(f"{self.backend_url}/available_models")
            if response.status_code == 200:
                return response.json()
            else:
                st.warning("Non è stato possibile recuperare l'elenco dei modelli. Usando valori predefiniti.")
                return {
                    "openai": [{"id": "gpt-4o-mini", "name": "GPT-4o Mini"}],
                    "claude": [{"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku"}],
                    "deepseek": [{"id": "deepseek-chat", "name": "DeepSeek Chat"}],
                    "ernie": [{"id": "ernie-bot-4", "name": "ERNIE Bot 4"}]
                }
        except Exception as e:
            st.warning(f"Errore nel recupero dei modelli: {e}")
            return {
                "openai": [{"id": "gpt-4o-mini", "name": "GPT-4o Mini"}],
                "claude": [{"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku"}],
                "deepseek": [{"id": "deepseek-chat", "name": "DeepSeek Chat"}],
                "ernie": [{"id": "ernie-bot-4", "name": "ERNIE Bot 4"}]
            }

    def get_models_for_provider(self, provider):
        """Restituisce i modelli disponibili per un provider specifico."""
        if provider in self.available_models:
            return self.available_models[provider]
        return []


class HintManager:
    """Gestisce gli hint per l'interpretazione dei dati."""

    def __init__(self, backend_url):
        """Inizializza il gestore degli hint."""
        self.backend_url = backend_url

    def get_hint_by_id(self, hint_id):
        """Recupera un hint specifico tramite il suo ID."""
        try:
            response = requests.get(f"{self.backend_url}/hints/{hint_id}")
            if response.status_code == 200:
                return response.json()
            else:
                st.warning(f"Errore nel recupero dell'hint con ID {hint_id}: {response.text}")
                return None
        except Exception as e:
            st.warning(f"Errore nel recupero dell'hint: {e}")
            return None

    def get_all_hints(self):
        """Recupera tutti gli hint dal backend."""
        try:
            response = requests.get(f"{self.backend_url}/hints")
            if response.status_code == 200:
                return response.json()
            else:
                st.warning("Non è stato possibile recuperare gli hint.")
                return []
        except Exception as e:
            st.warning(f"Errore nel recupero degli hint: {e}")
            return []

    def get_active_hints(self, hint_category=""):
        """Recupera solo gli hint attivi dal backend."""
        try:
            response = requests.get(f"{self.backend_url}/hints/active?hint_category={hint_category}")
            if response.status_code == 200:
                return response.json()
            else:
                st.warning("Non è stato possibile recuperare gli hint attivi.")
                return []
        except Exception as e:
            st.warning(f"Errore nel recupero degli hint attivi: {e}")
            return []

    def add_hint(self, hint_text, hint_category="generale"):
        """Aggiunge un nuovo hint."""
        try:
            response = requests.post(
                f"{self.backend_url}/hints",
                json={"hint_text": hint_text, "hint_category": hint_category}
            )
            if response.status_code == 200:
                return response.json().get("id")
            else:
                st.warning(f"Errore nell'aggiunta dell'hint: {response.text}")
                return None
        except Exception as e:
            st.warning(f"Errore nell'aggiunta dell'hint: {e}")
            return None

    def update_hint(self, hint_id, hint_text=None, hint_category=None, active=None):
        """Aggiorna un hint esistente."""
        try:
            payload = {}
            if hint_text is not None:
                payload["hint_text"] = hint_text
            if hint_category is not None:
                payload["hint_category"] = hint_category
            if active is not None:
                payload["active"] = active

            response = requests.put(
                f"{self.backend_url}/hints/{hint_id}",
                json=payload
            )

            if response.status_code == 200:
                return True
            else:
                st.warning(f"Errore nell'aggiornamento dell'hint: {response.text}")
                return False
        except Exception as e:
            st.warning(f"Errore nell'aggiornamento dell'hint: {e}")
            return False

    def delete_hint(self, hint_id):
        """Elimina un hint."""
        try:
            response = requests.delete(f"{self.backend_url}/hints/{hint_id}")
            if response.status_code == 200:
                return True
            else:
                st.warning(f"Errore nell'eliminazione dell'hint: {response.text}")
                return False
        except Exception as e:
            st.warning(f"Errore nell'eliminazione dell'hint: {e}")
            return False

    def toggle_hint_status(self, hint_id):
        """Attiva o disattiva un hint."""
        try:
            response = requests.put(f"{self.backend_url}/hints/{hint_id}/toggle")
            if response.status_code == 200:
                return True
            else:
                st.warning(f"Errore nel cambio di stato dell'hint: {response.text}")
                return False
        except Exception as e:
            st.warning(f"Errore nel cambio di stato dell'hint: {e}")
            return False

    def get_all_categories(self):
        """Recupera tutte le categorie dal backend."""
        try:
            response = requests.get(f"{self.backend_url}/categories")
            if response.status_code == 200:
                return response.json().get("categories", [])
            else:
                st.warning("Non è stato possibile recuperare le categorie.")
                return []
        except Exception as e:
            st.warning(f"Errore nel recupero delle categorie: {e}")
            return []

    def add_category(self, category_name):
        """Aggiunge una nuova categoria."""
        try:
            response = requests.post(
                f"{self.backend_url}/categories",
                json={"name": category_name}
            )
            if response.status_code == 200:
                return True
            else:
                st.warning(f"Errore nell'aggiunta della categoria: {response.text}")
                return False
        except Exception as e:
            st.warning(f"Errore nell'aggiunta della categoria: {e}")
            return False

    def delete_category(self, category_name, replace_with="generale"):
        """Elimina una categoria."""
        try:
            response = requests.delete(
                f"{self.backend_url}/categories",
                json={"name": category_name, "replace_with": replace_with}
            )
            if response.status_code == 200:
                return True
            else:
                st.warning(f"Errore nell'eliminazione della categoria: {response.text}")
                return False
        except Exception as e:
            st.warning(f"Errore nell'eliminazione della categoria: {e}")
            return False

    def export_hints(self):
        """Esporta gli hint in un file JSON."""
        try:
            response = requests.post(f"{self.backend_url}/hints/export")
            if response.status_code == 200:
                return True
            else:
                st.warning(f"Errore nell'esportazione degli hint: {response.text}")
                return False
        except Exception as e:
            st.warning(f"Errore nell'esportazione degli hint: {e}")
            return False

    def import_hints(self):
        """Importa gli hint da un file JSON."""
        try:
            response = requests.post(f"{self.backend_url}/hints/import")
            if response.status_code == 200:
                return True
            else:
                st.warning(f"Errore nell'importazione degli hint: {response.text}")
                return False
        except Exception as e:
            st.warning(f"Errore nell'importazione degli hint: {e}")
            return False


class UserInterface:
    """Gestisce l'interfaccia utente dell'applicazione."""

    def __init__(self, credentials_manager, llm_manager, hint_manager):
        """Inizializza l'interfaccia utente."""
        self.credentials_manager = credentials_manager
        self.llm_manager = llm_manager
        self.hint_manager = hint_manager

    def render_sidebar(self):
        """Visualizza la sidebar con le impostazioni."""
        st.sidebar.title("Configurazione")

        # Tab per organizzare la sidebar
        tab1, tab2, tab3 = st.sidebar.tabs(["🧠 LLM", "🔐 Connessione", "💾 Cache"])

        with tab1:
            self.render_llm_settings()

        with tab2:
            self.render_connection_settings()

        with tab3:
            self.render_cache_settings()

    def render_llm_settings(self):
        """Visualizza le impostazioni del LLM nella sidebar."""
        st.header("Configurazione LLM")

        # Selezione del provider LLM
        provider_options = [(key, value["name"]) for key, value in LLM_PROVIDERS.items()]
        selected_provider_index = 0

        # Trova l'indice del provider attualmente selezionato
        current_provider = self.credentials_manager.credentials.get("llm_provider", "openai")
        for i, (key, _) in enumerate(provider_options):
            if key == current_provider:
                selected_provider_index = i
                break

        selected_provider_name = st.selectbox(
            "Provider LLM",
            [name for _, name in provider_options],
            index=selected_provider_index
        )

        # Ottieni la chiave del provider selezionato
        selected_provider = next(key for key, value in LLM_PROVIDERS.items() if value["name"] == selected_provider_name)
        self.credentials_manager.credentials["llm_provider"] = selected_provider

        # Mostra i campi specifici per il provider
        provider_info = LLM_PROVIDERS[selected_provider]
        self.credentials_manager.credentials[provider_info["api_key_name"]] = st.text_input(
            f"Chiave API {provider_info['name']}",
            type="password",
            value=self.credentials_manager.credentials.get(provider_info["api_key_name"], "")
        )

        # Aggiungi il campo secret_key se richiesto dal provider
        if provider_info.get("requires_secret", False):
            self.credentials_manager.credentials[provider_info["secret_key_name"]] = st.text_input(
                f"Chiave Segreta {provider_info['name']}",
                type="password",
                value=self.credentials_manager.credentials.get(provider_info["secret_key_name"], "")
            )

        # Selezione del modello per il provider
        models = self.llm_manager.get_models_for_provider(selected_provider)
        model_options = [(model["id"], model["name"]) for model in models]

        if model_options:
            # Trova l'indice del modello attualmente selezionato
            current_model = self.credentials_manager.credentials.get(f"{selected_provider}_model", model_options[0][0])
            selected_model_index = 0
            for i, (model_id, _) in enumerate(model_options):
                if model_id == current_model:
                    selected_model_index = i
                    break

            selected_model_name = st.selectbox(
                f"Modello {provider_info['name']}",
                [name for _, name in model_options],
                index=selected_model_index
            )

            # Ottieni l'ID del modello selezionato
            selected_model = next(model_id for model_id, name in model_options if name == selected_model_name)
            self.credentials_manager.credentials[f"{selected_provider}_model"] = selected_model

        if st.button("💾 Salva configurazione"):
            self.credentials_manager.save_credentials()
            st.success("✅ Configurazione salvata con successo!")

    def render_connection_settings(self):
        """Visualizza le impostazioni di connessione nella sidebar."""
        st.header("SSH & Database")

        # Sezione SSH
        st.subheader("🔐 SSH")
        self.credentials_manager.credentials["ssh_host"] = st.text_input(
            "IP Server SSH",
            value=self.credentials_manager.credentials.get("ssh_host", "192.168.1.100")
        )
        self.credentials_manager.credentials["ssh_user"] = st.text_input(
            "Utente SSH",
            value=self.credentials_manager.credentials.get("ssh_user", "ubuntu")
        )
        self.credentials_manager.credentials["ssh_key"] = st.text_area(
            "Chiave Privata SSH",
            value=self.credentials_manager.credentials.get("ssh_key", "")
        )

        # Sezione Database
        st.subheader("🗄️ Database")

        # Selezione del tipo di database
        db_options = ["PostgreSQL", "SQL Server"]
        current_db_type = self.credentials_manager.credentials.get("db_type", "postgresql")
        default_index = 0 if current_db_type == "postgresql" else 1

        selected_db_type = st.selectbox(
            "Tipo di Database",
            db_options,
            index=default_index
        )

        # Mappa il valore selezionato al valore interno
        self.credentials_manager.credentials["db_type"] = "postgresql" if selected_db_type == "PostgreSQL" else "sqlserver"

        # Testo descrittivo basato sul tipo selezionato
        db_type_label = "PostgreSQL" if selected_db_type == "PostgreSQL" else "SQL Server"
        default_port = "5432" if selected_db_type == "PostgreSQL" else "1433"
        default_user = "postgres" if selected_db_type == "PostgreSQL" else "sa"

        self.credentials_manager.credentials["db_host"] = st.text_input(
            f"Host {db_type_label}",
            value=self.credentials_manager.credentials.get("db_host", "127.0.0.1")
        )
        self.credentials_manager.credentials["db_port"] = st.text_input(
            f"Porta {db_type_label}",
            value=self.credentials_manager.credentials.get("db_port", default_port)
        )
        self.credentials_manager.credentials["db_user"] = st.text_input(
            "Utente Database",
            value=self.credentials_manager.credentials.get("db_user", default_user)
        )
        self.credentials_manager.credentials["db_password"] = st.text_input(
            "Password Database",
            type="password",
            value=self.credentials_manager.credentials.get("db_password", "")
        )
        self.credentials_manager.credentials["db_name"] = st.text_input(
            "Nome Database",
            value=self.credentials_manager.credentials.get("db_name", "mio_database")
        )

        # Ottieni le categorie disponibili
        available_categories = self.hint_manager.get_all_categories()
        current_hint_category = self.credentials_manager.credentials.get("hint_category", "generale")

        # Trova l'indice della categoria corrente
        default_category_index = 0
        if current_hint_category in available_categories:
            default_category_index = available_categories.index(current_hint_category)

        self.credentials_manager.credentials["hint_category"] = st.selectbox(
            "Categoria hint",
            available_categories,
            index=default_category_index,
            key="config_hint_category"
        )

        if st.button("💾 Salva credenziali"):
            self.credentials_manager.save_credentials()
            st.success("✅ Credenziali salvate con successo!")

    def render_cache_settings(self):
        """Visualizza le impostazioni della cache nella sidebar."""
        st.header("Impostazioni Cache")

        if st.button("🔄 Esporta Hint"):
            if self.hint_manager.export_hints():
                st.success("✅ Hint esportati con successo!")
            else:
                st.error("❌ Errore nell'esportazione degli hint")

        if st.button("📥 Importa Hint"):
            if self.hint_manager.import_hints():
                st.success("✅ Hint importati con successo!")
            else:
                st.error("❌ Errore nell'importazione degli hint")

    def render_main_interface(self):
        """Visualizza l'interfaccia principale dell'applicazione."""

        # Aggiungi il logo sopra il titolo
        cola, colb = st.columns([1, 1])
        with cola:
            st.image("laundrybot_jit40.png", width=400)
        with colb:
            st.header(APP_TITLE)

        st.write("")
        st.write("")

        # Creiamo i tabs per le diverse sezioni
        tab1, tab2, tab3 = st.tabs(["📊 Analisi Dati", "✏️ Hint Interpretazione", "⚙️ Configurazioni"])

        # Inizializza il valore di ritorno
        action_data = {"action": None}

        # Renderizza i contenuti in entrambe le tab
        with tab1:
            action_data = self.render_analysis_tab()

        with tab2:
            self.render_hints_tab()

        with tab3:
            self.render_config_tab()

        # Ritorna il valore solo alla fine, dopo aver renderizzato entrambe le tab
        return action_data

    def render_analysis_tab(self):
        """Visualizza la tab di analisi dati con indicatori di progresso."""
        # Mostra il provider LLM attualmente selezionato
        provider = self.credentials_manager.credentials.get("llm_provider", "openai")
        provider_name = LLM_PROVIDERS[provider]["name"]
        model_name = self.credentials_manager.credentials.get(f"{provider}_model", "")

        st.info(f"🧠 Utilizzando {provider_name} - {model_name}")

        domande = []
        filter_hint_categ = self.credentials_manager.credentials.get("hint_category", "")
        if filter_hint_categ:
            domande = DOMANDE_SUGGERITE[filter_hint_categ] if filter_hint_categ in DOMANDE_SUGGERITE else []

        # Selettore domande
        domanda_selezionata = st.selectbox(
            "Seleziona una domanda",
            ["---"] + domande
        )
        domanda_input = st.text_area(
            label="Oppure scrivi una domanda libera",
            value="",
            height=200,
            max_chars=1000,
            help="Inserisci la tua descrizione qui. Massimo 1000 caratteri."
        )

        # Checkbox per forzare la rigenerazione della query senza cache
        force_no_cache = st.checkbox("Forza rigenerazione query SQL (ignora cache)")

        # Mostra gli hint attivi
        active_hints = self.hint_manager.get_active_hints(filter_hint_categ)
        if active_hints:
            with st.expander("📝 Hint attivi per l'interpretazione dei dati", expanded=False):
                for hint in active_hints:
                    st.write(f"**{hint['hint_category']}**: {hint['hint_text']}")

        # Inizializzazione dello stato dei pulsanti
        if "cerca_clicked" not in st.session_state:
            st.session_state.cerca_clicked = False
        if "refresh_clicked" not in st.session_state:
            st.session_state.refresh_clicked = False

        # Inizializzazione delle variabili di stato per la query in corso
        if "query_in_progress" not in st.session_state:
            st.session_state.query_in_progress = False
        if "query_id" not in st.session_state:
            st.session_state.query_id = None
        if "query_status" not in st.session_state:
            st.session_state.query_status = {}
        if "last_update_time" not in st.session_state:
            st.session_state.last_update_time = 0
        if "polling_active" not in st.session_state:
            st.session_state.polling_active = False

        # Pulsanti per le azioni
        col1, col2 = st.columns([1, 1])
        with col1:
            cerca_button = st.button(
                "🔍 Cerca",
                use_container_width=True,
                disabled=st.session_state.query_in_progress
            )
            if cerca_button:
                st.session_state.cerca_clicked = True
        with col2:
            refresh_button = st.button(
                "🔄 Riscansiona Database",
                use_container_width=True,
                disabled=st.session_state.query_in_progress
            )
            if refresh_button:
                st.session_state.refresh_clicked = True

        # Mostra il progresso se una query è in corso
        if st.session_state.query_in_progress and st.session_state.query_id:
            st.markdown("### 🔄 Elaborazione in corso")

            status_container = st.empty()
            progress_bar_container = st.empty()

            # Recupera stato attuale
            try:
                response = requests.get(f"{BACKEND_URL}/query_status/{st.session_state.query_id}")
                if response.status_code == 200:
                    status_data = response.json()
                    st.session_state.query_status = status_data

                    progress = status_data.get("progress", 0)
                    status = status_data.get("status", "")
                    step = status_data.get("step", "")
                    message = status_data.get("message", "")
                    attempts = status_data.get("attempts", 0)

                    icons = {
                        "starting": "🚀", "connecting": "🔌", "schema": "📊", "generating": "🧠",
                        "checking_cache": "🔍", "cache_hit": "💾", "cache_valid": "✅", "cache_invalid": "⚠️",
                        "executing": "⚙️", "processing": "📈", "visualizing": "📊", "completed": "✅",
                        "failed": "❌", "error": "⚠️", "retry": "🔄", "new_query": "📝", "saving_to_cache": "💾"
                    }
                    descriptions = {
                        "init": "Inizializzazione", "ssh_tunnel": "Connessione SSH", "db_schema": "Lettura schema DB",
                        "check_cache": "Controllo cache", "cache_hit": "Query trovata in cache",
                        "cache_valid": "Verifica cache", "cache_invalid": "Cache non valida",
                        "generate_sql": "Generazione SQL", "execute_sql": "Esecuzione query",
                        "process_results": "Analisi risultati", "generate_charts": "Creazione grafici",
                        "save_to_cache": "Salvataggio in cache", "completed": "Completato", "error": "Errore"
                    }

                    icon = icons.get(status, "🔄")
                    step_text = descriptions.get(step, step)
                    attempts_text = f" (Tentativo {attempts})" if attempts > 0 else ""

                    status_container.info(f"{icon} **{step_text}**{attempts_text}: {message}")
                    progress_bar_container.progress(progress / 100)

                    if status in ["completed", "failed", "error"]:
                        st.session_state.query_in_progress = False

                        if status == "completed" and "result" in status_data:
                            result_data = status_data["result"]
                            ResultVisualizer.display_results(result_data)
                        elif "error" in status_data:
                            st.error(f"❌ {status_data['error']}")
                        if "error_traceback" in status_data:
                            with st.expander("Dettagli errore"):
                                st.code(status_data["error_traceback"])

                else:
                    st.error(f"Errore polling: HTTP {response.status_code}")
                    st.session_state.query_in_progress = False

            except Exception as e:
                st.error(f"Errore nel polling: {str(e)}")
                st.session_state.query_in_progress = False

        return {
            "action": "cerca" if st.session_state.cerca_clicked else ("refresh" if st.session_state.refresh_clicked else None),
            "domanda": domanda_input if domanda_input else domanda_selezionata,
            "force_no_cache": force_no_cache
        }

    def render_hints_tab(self):
        """Visualizza la tab di gestione degli hint."""
        # Problema identificato: questa funzione viene chiamata, ma non mostra correttamente i contenuti

        # Assicuriamoci che il contenuto sia visibile
        st.header("✏️ Hint per l'interpretazione dei dati")

        # Aggiungiamo un container per garantire che il contenuto sia visibile
        hint_container = st.container()

        with hint_container:
            st.markdown("""
            Gli hint aiutano l'AI a interpretare correttamente i dati. Puoi aggiungere istruzioni specifiche
            su come interpretare tabelle, colonne o relazioni nel database.

            Ad esempio:
            - "I valori nella colonna 'stato_ordine' rappresentano il ciclo di vita dell'ordine"
            - "La tabella 'clienti' contiene sia aziende che persone fisiche"
            - "Le date sono in formato ISO e nel fuso orario UTC+1"
            """)

            # Tabella per visualizzare e gestire gli hint esistenti
            st.subheader("Hint esistenti")
            hints = self.hint_manager.get_all_hints()

            if not hints:
                st.info("Nessun hint presente. Aggiungi il primo hint per aiutare l'AI a interpretare i dati.")
            else:
                # Crea un dataframe per visualizzare gli hint
                df_hints = pd.DataFrame(hints)
                df_hints['status'] = df_hints['active'].apply(lambda x: "✅ Attivo" if x else "❌ Disattivato")
                df_hints = df_hints[['id', 'hint_category', 'hint_text', 'status']]
                df_hints.columns = ['ID', 'Categoria', 'Testo', 'Stato']

                st.dataframe(df_hints, hide_index=True)

                # Form per modificare o eliminare un hint
                st.subheader("Gestione degli hint esistenti")

                # Utilizziamo session_state per tenere traccia dell'hint selezionato
                if "selected_hint_id" not in st.session_state:
                    st.session_state.selected_hint_id = 0
                if "selected_hint_data" not in st.session_state:
                    st.session_state.selected_hint_data = None
                if "hint_action" not in st.session_state:
                    st.session_state.hint_action = "Modifica"

                # Funzione per caricare i dati dell'hint quando cambia l'ID
                def load_hint_data():
                    hint_id = st.session_state.hint_id_edit
                    if hint_id > 0:
                        hint_data = self.hint_manager.get_hint_by_id(hint_id)
                        if hint_data:
                            st.session_state.selected_hint_data = hint_data
                            st.session_state.selected_hint_id = hint_id
                        else:
                            st.warning(f"Hint con ID {hint_id} non trovato.")
                            st.session_state.selected_hint_data = None
                    else:
                        st.session_state.selected_hint_data = None

                # Contenitore per il feedback
                feedback_container = st.empty()

                col1, col2 = st.columns([1, 3])

                with col1:
                    # Utilizziamo key esplicite per evitare conflitti
                    hint_id_to_edit = st.number_input(
                        "ID Hint",
                        min_value=0,
                        step=1,
                        key="hint_id_edit",
                        on_change=load_hint_data
                    )

                with col2:
                    action = st.radio(
                        "Azione",
                        ["Modifica", "Attiva/Disattiva", "Elimina"],
                        key="hint_action",
                        on_change=lambda: setattr(st.session_state, 'hint_action', st.session_state.hint_action)
                    )

                # Mostriamo un'anteprima dell'hint selezionato
                if st.session_state.selected_hint_data:
                    hint_data = st.session_state.selected_hint_data

                    # Usiamo un expander per non prendere troppo spazio
                    with st.expander("Anteprima hint selezionato", expanded=True):
                        st.markdown(f"""
                        **ID**: {hint_data['id']}
                        **Categoria**: {hint_data['hint_category']}
                        **Stato**: {'✅ Attivo' if hint_data['active'] else '❌ Disattivato'}
                        **Testo**: {hint_data['hint_text']}
                        """)

                # Mostriamo campi differenti in base all'azione selezionata
                with st.form(key="edit_hint_form"):
                    if action == "Modifica":
                        # Preriempiamo i campi con i dati dell'hint selezionato
                        default_text = ""
                        default_category = ""

                        if st.session_state.selected_hint_data:
                            default_text = st.session_state.selected_hint_data["hint_text"]
                            default_category = st.session_state.selected_hint_data["hint_category"]

                        new_hint_text = st.text_area("Nuovo testo", key="new_hint_text", value=default_text)

                        # Ottieni le categorie disponibili
                        available_categories = self.hint_manager.get_all_categories()

                        # Trova l'indice della categoria corrente
                        default_category_index = 0
                        if default_category in available_categories:
                            default_category_index = available_categories.index(default_category)

                        new_hint_category = st.selectbox(
                            "Nuova categoria",
                            available_categories,
                            index=default_category_index,
                            key="new_hint_category"
                        )

                        update_button = st.form_submit_button("📝 Aggiorna hint")

                        if update_button and hint_id_to_edit > 0:
                            if self.hint_manager.update_hint(hint_id_to_edit, new_hint_text, new_hint_category):
                                feedback_container.success(f"✅ Hint {hint_id_to_edit} aggiornato con successo!")
                                # Ricarica i dati dell'hint
                                load_hint_data()
                            else:
                                feedback_container.error(f"❌ Errore nell'aggiornamento dell'hint {hint_id_to_edit}")

                    elif action == "Attiva/Disattiva":
                        # Mostriamo lo stato attuale dell'hint
                        current_status = ""
                        if st.session_state.selected_hint_data:
                            is_active = st.session_state.selected_hint_data["active"]
                            current_status = "✅ Attivo" if is_active else "❌ Disattivato"
                            st.write(f"Stato attuale: {current_status}")
                            st.write(f"Nuovo stato dopo il toggle: {'❌ Disattivato' if is_active else '✅ Attivo'}")

                        toggle_button = st.form_submit_button("🔄 Attiva/Disattiva hint")

                        if toggle_button and hint_id_to_edit > 0:
                            if self.hint_manager.toggle_hint_status(hint_id_to_edit):
                                feedback_container.success(f"✅ Stato dell'hint {hint_id_to_edit} modificato con successo!")
                                # Ricarica i dati dell'hint
                                load_hint_data()
                            else:
                                feedback_container.error(f"❌ Errore nella modifica dello stato dell'hint {hint_id_to_edit}")

                    elif action == "Elimina":
                        if st.session_state.selected_hint_data:
                            st.warning(f"""
                            ⚠️ Stai per eliminare definitivamente questo hint:

                            **ID**: {st.session_state.selected_hint_data['id']}
                            **Categoria**: {st.session_state.selected_hint_data['hint_category']}
                            **Testo**: {st.session_state.selected_hint_data['hint_text']}
                            """)
                        else:
                            st.warning("⚠️ Seleziona un hint da eliminare.")

                        delete_button = st.form_submit_button("🗑️ Elimina hint")

                        if delete_button and hint_id_to_edit > 0:
                            if self.hint_manager.delete_hint(hint_id_to_edit):
                                feedback_container.success(f"✅ Hint {hint_id_to_edit} eliminato con successo!")
                                # Resetta lo stato
                                st.session_state.selected_hint_data = None
                                st.session_state.selected_hint_id = 0
                            else:
                                feedback_container.error(f"❌ Errore nell'eliminazione dell'hint {hint_id_to_edit}")

            # Sezione per aggiungere un nuovo hint
            st.subheader("Aggiungi nuovo hint")

            with st.form(key="add_hint_form"):
                hint_text = st.text_area("Testo dell'hint", key="hint_text_input")

                # Ottieni le categorie dal backend
                hint_categories = self.hint_manager.get_all_categories()
                hint_category = st.selectbox("Categoria", hint_categories, key="hint_category_select")

                submit_button = st.form_submit_button("✅ Aggiungi hint")

                if submit_button and hint_text:
                    hint_id = self.hint_manager.add_hint(hint_text, hint_category)
                    if hint_id:
                        st.success(f"✅ Hint aggiunto con successo (ID: {hint_id})")
                        st.rerun()
                    else:
                        st.error("❌ Errore nell'aggiunta dell'hint")

    def render_config_tab(self):
        """Visualizza la tab di gestione configurazioni hint."""

        # Assicuriamoci che il contenuto sia visibile
        st.header("✏️ Configurazioni")

        # Aggiungiamo un container per garantire che il contenuto sia visibile
        config_container = st.container()

        with config_container:

            # Sezione per la gestione delle categorie
            st.subheader("Gestione Categorie")
            categories_col1, categories_col2 = st.columns([1, 1])

            with categories_col1:
                # Form per aggiungere una categoria
                with st.form(key="add_category_form"):
                    new_category = st.text_input("Nome nuova categoria", key="new_category_input")
                    add_category_button = st.form_submit_button("➕ Aggiungi Categoria")

                    if add_category_button and new_category:
                        success = self.hint_manager.add_category(new_category)
                        if success:
                            st.success(f"✅ Categoria '{new_category}' aggiunta con successo!")
                            st.rerun()
                        else:
                            st.error(f"❌ La categoria '{new_category}' esiste già o si è verificato un errore")

            with categories_col2:
                # Form per eliminare una categoria
                with st.form(key="delete_category_form"):
                    # Ottieni le categorie disponibili
                    available_categories = self.hint_manager.get_all_categories()

                    # Filtra la categoria "generale" che non può essere eliminata
                    delete_options = [cat for cat in available_categories if cat != "generale"]

                    if not delete_options:
                        st.info("Non ci sono categorie che possono essere eliminate.")
                        st.form_submit_button("🗑️ Elimina Categoria", disabled=True)
                    else:
                        category_to_delete = st.selectbox(
                            "Categoria da eliminare",
                            options=delete_options,
                            key="category_to_delete"
                        )

                        # Opzioni per la sostituzione (tutte le categorie tranne quella da eliminare)
                        replacement_options = [cat for cat in available_categories if cat != category_to_delete]
                        replacement_category = st.selectbox(
                            "Sostituisci con",
                            options=replacement_options,
                            index=0,  # Default alla prima opzione (probabilmente "generale")
                            key="replacement_category"
                        )

                        delete_button = st.form_submit_button("🗑️ Elimina Categoria")

                        if delete_button and category_to_delete:
                            success = self.hint_manager.delete_category(category_to_delete, replacement_category)
                            if success:
                                st.success(f"✅ Categoria '{category_to_delete}' eliminata con successo!")
                                st.rerun()
                            else:
                                st.error(f"❌ Errore nell'eliminazione della categoria '{category_to_delete}'")

            # Mostra le categorie esistenti
            st.subheader("Categorie Disponibili")
            available_categories = self.hint_manager.get_all_categories()
            if available_categories:
                # Visualizza le categorie in una griglia di chip
                categories_html = ""
                for category in available_categories:
                    categories_html += (
                        '<span style="background-color:grey;padding:5px 10px;'
                        f'margin:5px;border-radius:15px;display:inline-block">{category}</span>'
                    )

                st.markdown(categories_html, unsafe_allow_html=True)
            else:
                st.info("Nessuna categoria disponibile.")

            st.markdown("---")  # Separatore visivo


class BackendClient:
    """Gestisce le chiamate API al backend."""

    def __init__(self, backend_url):
        """Inizializza il client backend."""
        self.backend_url = backend_url

    def execute_query(self, domanda, llm_config, ssh_config, db_config, force_no_cache=False):
        """Invia la richiesta di query e restituisce l'ID."""
        response = requests.post(
            f"{self.backend_url}/query",
            json={
                "domanda": domanda,
                "llm_config": llm_config,
                "ssh_config": ssh_config,
                "db_config": db_config,
                "force_no_cache": force_no_cache
            }
        )
        return response

    def get_query_status(self, query_id):
        """Recupera lo stato di una query."""
        response = requests.get(f"{self.backend_url}/query_status/{query_id}")
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

        # Mostra il provider LLM utilizzato
        if "llm_provider" in data:
            provider = data.get("llm_provider", "openai")
            provider_name = LLM_PROVIDERS.get(provider, {}).get("name", provider.upper())
            st.info(f"🧠 Analisi generata con {provider_name}")

        # Mostra descrizione AI
        st.subheader("📖 Interpretazione AI:")
        st.write(data['descrizione'])

        # Mostra query SQL utilizzata
        with st.expander("🔍 Visualizza query SQL", expanded=False):
            st.code(data['query_sql'], language="sql")

        # Notifica sulla cache
        if data.get("cache_used", False):
            st.success("✅ Query SQL presa dalla cache!")
        else:
            st.warning("⚠️ La query è stata rigenerata senza cache.")

        # Visualizza i dati in tabella
        df = pd.DataFrame(data["dati"])
        st.subheader("📋 Dati Analizzati:")
        st.dataframe(df)

        # Scarica il file Excel
        if not df.empty:
            output = BytesIO()
            df.to_excel(output, index=False, engine='xlsxwriter')
            output.seek(0)
            st.download_button(
                label="📥 Scarica Excel",
                data=output,
                file_name="analisi.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        # Mostra i grafici
        if "grafici" in data and data["grafici"]:
            st.subheader("📊 Grafici Generati dall'AI")
            st.image(data["grafici"], caption="Grafico Generato", use_container_width=True)


def main():
    """Funzione principale dell'applicazione."""
    # Inizializzazione dei gestori
    auth_manager = AuthManager()
    credentials_manager = CredentialsManager(CREDENTIALS_FILE)
    llm_manager = LLMManager(BACKEND_URL)
    hint_manager = HintManager(BACKEND_URL)
    ui = UserInterface(credentials_manager, llm_manager, hint_manager)
    backend_client = BackendClient(BACKEND_URL)

    # Verifica del login
    if not auth_manager.check_login():
        auth_manager.login_page()
        return

    # Logout nella sidebar
    auth_manager.logout()

    # Debugging dello stato della sessione (opzionale)
    # st.sidebar.write("Debug - query_in_progress:", st.session_state.get("query_in_progress", False))
    # st.sidebar.write("Debug - query_id:", st.session_state.get("query_id", None))

    # Rendering della sidebar
    ui.render_sidebar()

    # Gestione di query in corso
    if st.session_state.get("query_in_progress", False) and st.session_state.get("query_id"):
        # Già in elaborazione, continua con l'interfaccia principale
        ui_data = ui.render_main_interface()
    else:
        # Rendering dell'interfaccia principale per nuove query
        ui_data = ui.render_main_interface()

        # Gestione dell'azione "Cerca"
        if ui_data.get("action") == "cerca":
            st.session_state.cerca_clicked = False

            domanda = ui_data["domanda"]
            if domanda and domanda != "---":
                # Mostra messaggio di avvio
                st.info("🚀 Avvio analisi...")

                # Ottieni la configurazione corrente
                llm_config = credentials_manager.get_llm_config()

                # Esegui la richiesta
                try:
                    response = backend_client.execute_query(
                        domanda=domanda,
                        llm_config=llm_config,
                        ssh_config=credentials_manager.get_ssh_config(),
                        db_config=credentials_manager.get_db_config(),
                        force_no_cache=ui_data["force_no_cache"]
                    )

                    if response.status_code == 200:
                        data = response.json()
                        # Imposta stato di elaborazione e ID query
                        st.session_state.query_in_progress = True
                        st.session_state.query_id = data.get("query_id")
                        st.success("🚀 Analisi avviata! La pagina verrà aggiornata automaticamente...")
                        # Forza il refresh con un piccolo ritardo per assicurarsi che lo stato sia salvato
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error(f"❌ Errore nell'elaborazione della richiesta: {response.text}")
                except Exception as e:
                    st.error(f"❌ Errore nella comunicazione col backend: {str(e)}")
            else:
                st.warning("Per favore, inserisci una domanda da analizzare.")

        # Gestione dell'azione "Riscansiona Database"
        if ui_data.get("action") == "refresh":
            st.session_state.refresh_clicked = False

            st.info("Avvio riscansione del database...")
            try:
                response = backend_client.refresh_schema(
                    ssh_config=credentials_manager.get_ssh_config(),
                    db_config=credentials_manager.get_db_config()
                )

                if response.status_code == 200:
                    st.success("✅ Struttura del database aggiornata!")
                else:
                    st.error(f"❌ Errore durante la riscansione del database: {response.text}")
            except Exception as e:
                st.error(f"❌ Errore nella comunicazione col backend: {str(e)}")


# Punto di ingresso dell'applicazione
if __name__ == "__main__":
    main()
