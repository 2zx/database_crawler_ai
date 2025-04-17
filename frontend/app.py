"""
Punto di ingresso principale per l'applicazione Streamlit.
"""
from frontend.ui import UserInterface
from frontend.api import BackendClient, LLMManager, HintManager, RatingManager
from frontend.utils import CredentialsManager, ResultVisualizer
from frontend.auth import AuthManager
from frontend.config import STREAMLIT_CONFIG, BACKEND_URL, CREDENTIALS_FILE
import sys
import os
import streamlit as st   # type: ignore
import logging
import time

# Aggiungi la directory padre al path di Python
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))

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
    rating_manager = RatingManager(BACKEND_URL)

    # Verifica del login
    if not auth_manager.check_login():
        auth_manager.login_page()
        return

    # Logout nella sidebar
    auth_manager.logout()

    # Initializza l'interfaccia utente
    ui = UserInterface(credentials_manager, llm_manager,
                       hint_manager, backend_client, rating_manager)

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
                        st.session_state.query_in_progress = False
                        st.error(
                            f"❌ Errore nell'elaborazione della richiesta: {response.text}")
                except Exception as e:
                    st.session_state.query_in_progress = False
                    st.error(
                        f"❌ Errore nella comunicazione col backend: {str(e)}")
            else:
                st.session_state.query_in_progress = False
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
                    st.error(
                        f"❌ Errore durante la riscansione del database: {response.text}")
            except Exception as e:
                st.error(f"❌ Errore nella comunicazione col backend: {str(e)}")

    # Gestione del salvataggio dei risultati (inclusi errori)
    query_completed = (not st.session_state.get("query_in_progress", False) and
                       st.session_state.get("query_id") and
                       not st.session_state.get("results_saved", False))

    if query_completed:
        # Verifica se abbiamo risultati o solo stato (che può contenere errori)
        if st.session_state.get("query_results"):
            results_data = st.session_state.query_results
            # Aggiungi il campo domanda ai risultati se mancante
            if "domanda" not in results_data and "domanda" in st.session_state.query_status:
                results_data["domanda"] = st.session_state.query_status.get(
                    "domanda", "")
        else:
            # Crea un risultato minimo con le informazioni di errore disponibili
            results_data = {
                "domanda": st.session_state.query_status.get("domanda", ""),
                "query_sql": st.session_state.query_status.get("query_sql", ""),
                "descrizione": "Errore nell'elaborazione: " + st.session_state.query_status.get("error", "Errore sconosciuto"),
                "dati": [],
                "grafici": None,
                "llm_provider": st.session_state.query_status.get("llm_provider", ""),
                "cache_used": st.session_state.query_status.get("cache_used", False),
                "error": st.session_state.query_status.get("error", ""),
                "error_traceback": st.session_state.query_status.get("error_traceback", "")
            }

        # Salva i risultati nel database
        if ResultVisualizer.save_result_to_db(
                results_data,
                rating_manager,
                st.session_state.query_id):
            logger.info(
                f"Risultati salvati con successo per query ID: {st.session_state.query_id}")
            st.session_state.results_saved = True
        else:
            logger.error(
                f"Errore nel salvataggio dei risultati per query ID: {st.session_state.query_id}")


# Punto di ingresso dell'applicazione
if __name__ == "__main__":
    main()
