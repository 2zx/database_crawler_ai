"""
Gestisce la visualizzazione dei risultati dell'analisi.
"""
import pandas as pd     # type: ignore
import streamlit as st      # type: ignore
from io import BytesIO
from frontend.config import LLM_PROVIDERS
import logging

# Configurazione del logging
logger = logging.getLogger(__name__)


class ResultVisualizer:
    """Gestisce la visualizzazione dei risultati dell'analisi."""

    @staticmethod
    def display_results(data, rating_manager=None, query_id=None):
        """
        Visualizza i risultati dell'analisi.

        Args:
            data (dict): Dati risultanti dall'analisi
            rating_manager: Gestore delle valutazioni (opzionale)
            query_id (str): ID della query per le valutazioni (opzionale)
        """
        # Mostra il provider LLM utilizzato
        if "llm_provider" in data:
            provider = data.get("llm_provider", "openai")
            provider_name = LLM_PROVIDERS.get(
                provider, {}).get("name", provider.upper())
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
            st.image(data["grafici"], caption="Grafico Generato",
                     use_container_width=True)

        # Sistema di valutazione (solo se rating_manager e query_id sono forniti)
        if rating_manager and query_id:
            st.subheader("✅ Valuta questa analisi")

            # Verifica se esiste già una valutazione
            existing_rating = rating_manager.get_rating(query_id)

            # Imposta i valori predefiniti in base alla valutazione esistente
            if existing_rating:
                default_positive = existing_rating.get("positive", True)
                default_feedback = existing_rating.get("feedback", "")
            else:
                default_positive = True
                default_feedback = ""

            # Key per lo stato
            if f"rating_positive_{query_id}" not in st.session_state:
                st.session_state[f"rating_positive_{query_id}"] = default_positive

            if f"rating_feedback_{query_id}" not in st.session_state:
                st.session_state[f"rating_feedback_{query_id}"] = default_feedback

            # Interfaccia di valutazione
            col1, col2 = st.columns([1, 3])

            with col1:
                # Pulsanti per voto positivo/negativo
                if st.button("👍 Utile", key=f"rating_pos_{query_id}",
                             use_container_width=True,
                             type="primary" if st.session_state[f"rating_positive_{query_id}"] else "secondary"):
                    st.session_state[f"rating_positive_{query_id}"] = True
                    st.rerun()

                if st.button("👎 Non utile", key=f"rating_neg_{query_id}",
                             use_container_width=True,
                             type="primary" if not st.session_state[f"rating_positive_{query_id}"] else "secondary"):
                    st.session_state[f"rating_positive_{query_id}"] = False
                    st.rerun()

            with col2:
                # Campo per il feedback
                feedback = st.text_area(
                    "Feedback (opzionale)",
                    value=st.session_state[f"rating_feedback_{query_id}"],
                    key=f"feedback_text_{query_id}",
                    height=100
                )

                # Pulsante di invio
                if st.button("Invia valutazione", key=f"submit_rating_{query_id}"):
                    if rating_manager.submit_rating(
                        query_id=query_id,
                        domanda=data.get("domanda", ""),
                        query_sql=data.get("query_sql", ""),
                        positive=st.session_state[f"rating_positive_{query_id}"],
                        feedback=feedback,
                        llm_provider=data.get("llm_provider")
                    ):
                        st.success("✅ Valutazione inviata con successo!")
                    else:
                        st.error("❌ Errore nell'invio della valutazione.")

            # Se esiste già una valutazione, mostro un messaggio
            if existing_rating:
                st.info(
                    "Hai già valutato questa analisi. Puoi modificare la tua valutazione sopra.")

        # Mostra domande correlate (se disponibili)
        if "related_questions" in data and data["related_questions"]:
            st.subheader("🔄 Possibili approfondimenti:")

            for i, question in enumerate(data["related_questions"]):
                col1, col2 = st.columns([9, 1])
                with col1:
                    st.write(f"{i+1}. {question}")
                with col2:
                    # Funzione di callback per il click
                    def create_click_handler(q):
                        def click_handler():
                            st.session_state.domanda_suggerita = q
                            logger.info(
                                f"Domanda selezionata create_click_handler: {q}")

                        return click_handler

                    # Crea un bottone con callback personalizzato
                    st.button(
                        "🔍", key=f"btn_{i}_{hash(question)%10000}",
                        on_click=create_click_handler(question)
                    )

    @staticmethod
    def save_result_to_db(data, rating_manager, query_id):
        """
        Salva i risultati dell'analisi nel database.

        Args:
            data (dict): Dati risultanti dall'analisi
            rating_manager: Gestore delle valutazioni
            query_id (str): ID della query

        Returns:
            bool: True se il salvataggio è riuscito, False altrimenti
        """
        try:
            # Estrai solo i primi 1000 record di dati per evitare problemi di dimensione
            dati_limitati = data.get("dati", [])[
                :1000] if data.get("dati") else []

            return rating_manager.save_analysis_result(
                query_id=query_id,
                domanda=data.get("domanda", ""),
                query_sql=data.get("query_sql", ""),
                descrizione=data.get("descrizione", ""),
                dati=dati_limitati,
                grafico_path=data.get("grafici", ""),
                llm_provider=data.get("llm_provider"),
                cache_used=data.get("cache_used", False),
                execution_time=data.get("execution_time")
            )
        except Exception as e:
            logger.error(f"Errore nel salvataggio del risultato: {e}")
            return False
