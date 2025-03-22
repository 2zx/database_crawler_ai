"""
Frontend Streamlit per l'analisi AI di database PostgreSQL attraverso tunnel SSH.
Include sistema di login, gestione configurazioni tramite file .env,
sistema di hint per l'interpretazione dei dati e supporto per diversi provider LLM.
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

# Configurazione dei provider LLM
LLM_PROVIDERS = {
    "openai": {"name": "OpenAI", "api_key_name": "openai_api_key", "requires_secret": False},
    "claude": {"name": "Anthropic Claude", "api_key_name": "claude_api_key", "requires_secret": False},
    "deepseek": {"name": "DeepSeek", "api_key_name": "deepseek_api_key", "requires_secret": False},
    "ernie": {"name": "Baidu ERNIE", "api_key_name": "ernie_api_key", "requires_secret": True,
              "secret_key_name": "ernie_secret_key"}
}


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

    def get_active_hints(self):
        """Recupera solo gli hint attivi dal backend."""
        try:
            response = requests.get(f"{self.backend_url}/hints/active")
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

    def get_hint_categories(self):
        """Recupera le categorie di hint suggerite."""
        try:
            response = requests.get(f"{self.backend_url}/hints/categories")
            if response.status_code == 200:
                return response.json().get("categories", ["generale"])
            else:
                return ["generale"]
        except Exception as e:
            st.warning(f"Errore nel recupero delle categorie: {e}")
            return ["generale"]

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
        st.subheader("🗄️ PostgreSQL")
        self.credentials_manager.credentials["db_host"] = st.text_input(
            "Host PostgreSQL",
            value=self.credentials_manager.credentials.get("db_host", "127.0.0.1")
        )
        self.credentials_manager.credentials["db_port"] = st.text_input(
            "Porta PostgreSQL",
            value=self.credentials_manager.credentials.get("db_port", "5432")
        )
        self.credentials_manager.credentials["db_user"] = st.text_input(
            "Utente Database",
            value=self.credentials_manager.credentials.get("db_user", "postgres")
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
        st.title(APP_TITLE)

        # Creiamo i tabs per le diverse sezioni
        tab1, tab2 = st.tabs(["📊 Analisi Dati", "✏️ Hint Interpretazione"])

        # Inizializza il valore di ritorno
        action_data = {"action": None}

        # Renderizza i contenuti in entrambe le tab
        with tab1:
            action_data = self.render_analysis_tab()

        with tab2:
            self.render_hints_tab()

        # Ritorna il valore solo alla fine, dopo aver renderizzato entrambe le tab
        return action_data

    def render_analysis_tab(self):
        """Visualizza la tab di analisi dati."""
        # Mostra il provider LLM attualmente selezionato
        provider = self.credentials_manager.credentials.get("llm_provider", "openai")
        provider_name = LLM_PROVIDERS[provider]["name"]
        model_name = self.credentials_manager.credentials.get(f"{provider}_model", "")

        st.info(f"🧠 Utilizzando {provider_name} - {model_name}")

        # Selettore domande
        domanda_selezionata = st.selectbox(
            "Seleziona una domanda",
            ["Scrivi la tua domanda..."] + DOMANDE_SUGGERITE
        )
        domanda_input = st.text_input("Oppure scrivi una domanda libera:")

        # Checkbox per forzare la rigenerazione della query senza cache
        force_no_cache = st.checkbox("Forza rigenerazione query SQL (ignora cache)")

        # Mostra gli hint attivi
        active_hints = self.hint_manager.get_active_hints()
        if active_hints:
            with st.expander("📝 Hint attivi per l'interpretazione dei dati", expanded=False):
                for hint in active_hints:
                    st.write(f"**{hint['hint_category']}**: {hint['hint_text']}")

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

            # Sezione per aggiungere un nuovo hint
            st.subheader("Aggiungi nuovo hint")

            with st.form(key="add_hint_form"):
                hint_text = st.text_area("Testo dell'hint", key="hint_text_input")

                # Ottieni le categorie dal backend
                hint_categories = self.hint_manager.get_hint_categories()
                hint_category = st.selectbox("Categoria", hint_categories, key="hint_category_select")

                submit_button = st.form_submit_button("✅ Aggiungi hint")

                if submit_button and hint_text:
                    hint_id = self.hint_manager.add_hint(hint_text, hint_category)
                    if hint_id:
                        st.success(f"✅ Hint aggiunto con successo (ID: {hint_id})")
                        st.experimental_rerun()
                    else:
                        st.error("❌ Errore nell'aggiunta dell'hint")

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

                st.dataframe(df_hints)

                # Form per modificare o eliminare un hint
                st.subheader("Gestione degli hint esistenti")

                with st.form(key="edit_hint_form"):
                    col1, col2 = st.columns([1, 3])

                    with col1:
                        # Utilizziamo key esplicite per evitare conflitti
                        hint_id_to_edit = st.number_input("ID Hint", min_value=1, step=1, key="hint_id_edit")

                    with col2:
                        action = st.radio("Azione", ["Modifica", "Attiva/Disattiva", "Elimina"], key="hint_action")

                    # Mostriamo campi differenti in base all'azione selezionata
                    if action == "Modifica":
                        new_hint_text = st.text_area("Nuovo testo", key="new_hint_text")
                        new_hint_category = st.selectbox("Nuova categoria", hint_categories, key="new_hint_category")

                        update_button = st.form_submit_button("📝 Aggiorna hint")

                        if update_button:
                            if self.hint_manager.update_hint(hint_id_to_edit, new_hint_text, new_hint_category):
                                st.success(f"✅ Hint {hint_id_to_edit} aggiornato con successo!")
                                st.experimental_rerun()
                            else:
                                st.error(f"❌ Errore nell'aggiornamento dell'hint {hint_id_to_edit}")

                    elif action == "Attiva/Disattiva":
                        toggle_button = st.form_submit_button("🔄 Attiva/Disattiva hint")

                        if toggle_button:
                            if self.hint_manager.toggle_hint_status(hint_id_to_edit):
                                st.success(f"✅ Stato dell'hint {hint_id_to_edit} modificato con successo!")
                                st.experimental_rerun()
                            else:
                                st.error(f"❌ Errore nella modifica dello stato dell'hint {hint_id_to_edit}")

                    elif action == "Elimina":
                        st.warning("⚠️ Questa operazione eliminerà definitivamente l'hint selezionato.")
                        delete_button = st.form_submit_button("🗑️ Elimina hint")

                        if delete_button:
                            if self.hint_manager.delete_hint(hint_id_to_edit):
                                st.success(f"✅ Hint {hint_id_to_edit} eliminato con successo!")
                                st.experimental_rerun()
                            else:
                                st.error(f"❌ Errore nell'eliminazione dell'hint {hint_id_to_edit}")


class BackendClient:
    """Gestisce le chiamate API al backend."""

    def __init__(self, backend_url):
        """Inizializza il client backend."""
        self.backend_url = backend_url

    def execute_query(self, domanda, llm_config, ssh_config, db_config, force_no_cache=False):
        """Esegue una query al backend."""
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

        # Mostra il provider LLM utilizzato
        if "llm_provider" in data:
            provider = data.get("llm_provider", "openai")
            provider_name = LLM_PROVIDERS.get(provider, {}).get("name", provider.upper())
            st.info(f"🧠 Analisi generata con {provider_name}")

        # Mostra descrizione AI
        st.subheader("📖 Interpretazione AI:")
        st.write(data['descrizione'])

        # Mostra query SQL utilizzata
        st.subheader("🔍 Query SQL:")
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

    # Rendering della sidebar
    ui.render_sidebar()

    # Rendering dell'interfaccia principale
    ui_data = ui.render_main_interface()

    # Gestione dell'azione "Cerca"
    if ui_data.get("action") == "cerca":
        st.session_state.cerca_clicked = False

        domanda = ui_data["domanda"]
        if domanda and domanda != "Scrivi la tua domanda...":
            st.info("Analisi in corso...")

            # Ottieni la configurazione corrente
            llm_config = credentials_manager.get_llm_config()

            response = backend_client.execute_query(
                domanda=domanda,
                llm_config=llm_config,
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
                st.error(f"❌ Errore nell'elaborazione della richiesta: {response.text}")
        else:
            st.warning("Per favore, inserisci una domanda da analizzare.")

    # Gestione dell'azione "Riscansiona Database"
    if ui_data.get("action") == "refresh":
        st.session_state.refresh_clicked = False

        st.info("Avvio riscansione del database...")
        response = backend_client.refresh_schema(
            ssh_config=credentials_manager.get_ssh_config(),
            db_config=credentials_manager.get_db_config()
        )

        if response.status_code == 200:
            st.success("✅ Struttura del database aggiornata!")
        else:
            st.error(f"❌ Errore durante la riscansione del database: {response.text}")


# Punto di ingresso dell'applicazione
if __name__ == "__main__":
    main()
