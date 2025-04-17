"""
Gestisce l'interfaccia utente per la tab di analisi dati.
"""
import streamlit as st  # type: ignore
import time
import logging
from frontend.config import LLM_PROVIDERS, DOMANDE_SUGGERITE
from frontend.utils import ResultVisualizer

# Configurazione del logging
logger = logging.getLogger(__name__)


class AnalysisTab:
    """Gestisce l'interfaccia per la tab di analisi dati."""

    def __init__(self, credentials_manager, llm_manager, hint_manager, backend_client):
        """
        Inizializza la tab di analisi.

        Args:
            credentials_manager: Gestore delle credenziali
            llm_manager: Gestore dei modelli LLM
            hint_manager: Gestore degli hint
            backend_client: Client per comunicazione con il backend
        """
        self.credentials_manager = credentials_manager
        self.llm_manager = llm_manager
        self.hint_manager = hint_manager
        self.backend_client = backend_client

    def render(self):
        """
        Visualizza la tab di analisi dati con indicatori di progresso.

        Returns:
            dict: Dati dell'azione da eseguire
        """

        # Mostra il provider LLM attualmente selezionato
        provider = self.credentials_manager.credentials.get("llm_provider", "openai")
        provider_name = LLM_PROVIDERS[provider]["name"]
        model_name = self.credentials_manager.credentials.get(f"{provider}_model", "")

        st.info(f"🧠 LLM {provider_name} - {model_name}")

        # Ottieni le domande suggerite dalla categoria corrente
        filter_hint_categ = self.credentials_manager.credentials.get("hint_category", "")
        domande = []
        if filter_hint_categ and filter_hint_categ in DOMANDE_SUGGERITE:
            domande = DOMANDE_SUGGERITE[filter_hint_categ]

        # Inizializza lo stato domande
        if "domanda_corrente" not in st.session_state:
            st.session_state.domanda_corrente = ""
        if "domanda_suggerita" not in st.session_state:
            st.session_state.domanda_suggerita = ""
        if "domanda_selector" not in st.session_state:
            st.session_state.domanda_selector = "---"

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

        # Selettore domande
        # Un callback che viene attivato quando cambia la selezione
        def on_domanda_change():
            logger.info(f"Domanda selezionata on_domanda_change: {st.session_state.domanda_selector}")
            selected = st.session_state.domanda_selector
            st.session_state.domanda_corrente = selected if selected != "---" else ""

        logger.info(f"Domanda domanda_suggerita: {st.session_state.domanda_suggerita}")
        logger.info(f"Domanda domanda_corrente: {st.session_state.domanda_corrente}")
        logger.info(f"Domanda domanda_selector: {st.session_state.domanda_selector}")

        if st.session_state.domanda_suggerita:
            st.session_state.domanda_selector = "---"
            st.session_state.domanda_corrente = st.session_state.domanda_suggerita
            st.session_state.domanda_suggerita = ""

        st.selectbox(
            "Seleziona una domanda",
            ["---"] + domande,
            key="domanda_selector",
            on_change=on_domanda_change
        )

        # Modifica all'input della domanda
        domanda_testo = st.text_area(
            label="Oppure scrivi una domanda libera",
            height=200,
            max_chars=1000,
            key="domanda_corrente",
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

        # Pulsanti per le azioni
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            # Callback quando viene premuto il bottone Cerca
            def on_cerca_click():
                st.session_state.cerca_clicked = True
                # Salviamo la domanda corrente (sia da selectbox che da text_area)
                if domanda_testo:  # Se c'è qualcosa nella textarea, prendi quella
                    st.session_state.domanda_corrente = domanda_testo

            st.button(
                "🔍 Cerca",
                use_container_width=True,
                disabled=st.session_state.query_in_progress,
                on_click=on_cerca_click
            )

        # Gestione query in corso, polling, ecc.
        if st.session_state.query_in_progress and st.session_state.query_id:
            st.markdown("### 🔄 Elaborazione")
            status_container = st.empty()
            progress_bar_container = st.empty()

            try:
                response = self.backend_client.get_query_status(st.session_state.query_id)
                if response.status_code == 200:
                    status_data = response.json()
                    st.session_state.query_status = status_data

                    logger.info(f"Polling status: {status_data}")

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

                        if "error" in status_data:
                            st.error(f"❌ {status_data['error']}")
                        elif status == "completed" and "result" in status_data:
                            result_data = status_data["result"]
                            ResultVisualizer.display_results(result_data)

                        if "error_traceback" in status_data:
                            with st.expander("Dettagli errore"):
                                st.code(status_data["error_traceback"])

                    else:
                        # 🔁 Ripeti polling dopo 2 secondi
                        time.sleep(2.5)
                        st.rerun()

                else:
                    st.error(f"Errore polling: HTTP {response.status_code}")
                    st.session_state.query_in_progress = False

            except Exception as e:
                st.error(f"Errore nel polling: {str(e)}")
                st.session_state.query_in_progress = False
                st.session_state.query_id = None
                st.session_state.query_status = {}

        return {
            "action": "cerca" if st.session_state.cerca_clicked else ("refresh" if st.session_state.refresh_clicked else None),
            "domanda": st.session_state.domanda_corrente,
            "force_no_cache": force_no_cache
        }
