"""
Punto di ingresso principale per l'applicazione Streamlit.
"""
import sys
import os
import streamlit as st   # type: ignore
import logging
import time

# Aggiungi la directory padre al path di Python
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importazioni dai moduli refactored
from frontend.config import STREAMLIT_CONFIG, BACKEND_URL, CREDENTIALS_FILE
from frontend.auth import AuthManager
from frontend.utils import CredentialsManager
from frontend.api import BackendClient, LLMManager, HintManager
from frontend.ui import UserInterface

# Configurazione del logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurazione della pagina Streamlit
st.set_page_config(**STREAMLIT_CONFIG)


def main():
    """Funzione principale dell'applicazione."""
    # Inizializzazione dei gestori
    auth_manager = AuthManager()
    credentials_manager = CredentialsManager(CREDENTIALS_FILE)
    llm_manager = LLMManager(BACKEND_URL)
    hint_manager = HintManager(BACKEND_URL)
    backend_client = BackendClient(BACKEND_URL)

    # Verifica del login
    if not auth_manager.check_login():
        auth_manager.login_page()
        return

    # Logout nella sidebar
    auth_manager.logout()

    # Initializza l'interfaccia utente
    ui = UserInterface(credentials_manager, llm_manager, hint_manager, backend_client)

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
