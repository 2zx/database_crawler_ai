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
        st.dataframe(df, hide_index=True)

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

            # Interfaccia di valutazione con design migliorato
            col1, col2 = st.columns([1, 3])

            with col1:
                st.write("##### Valutazione:")

                # Usiamo le opzioni di selettore più eleganti
                rating_options = {
                    "positive": "😀 Utile",
                    "negative": "😕 Non utile"
                }

                # Convertiamo il valore booleano in una delle tre opzioni
                if f"rating_value_{query_id}" not in st.session_state:
                    if existing_rating:
                        st.session_state[f"rating_value_{query_id}"] = "positive" if existing_rating.get(
                            "positive", True) else "negative"
                    else:
                        st.session_state[f"rating_value_{query_id}"] = ""

                # Funzione di callback per il cambio di valutazione
                def on_rating_change():
                    selected = st.session_state[f"rating_select_{query_id}"]
                    st.session_state[f"rating_value_{query_id}"] = selected
                    st.session_state[f"rating_positive_{query_id}"] = selected in [
                        "positive", "neutral"]

                # Radio con stile migliorato
                st.radio(
                    "Quanto ti è stata utile questa analisi?",
                    options=list(rating_options.keys()),
                    format_func=lambda x: rating_options[x],
                    key=f"rating_select_{query_id}",
                    index=list(rating_options.keys()).index(
                        st.session_state[f"rating_value_{query_id}"]) if st.session_state[f"rating_value_{query_id}"] else 0,
                    on_change=on_rating_change,
                    horizontal=True,
                    label_visibility="collapsed"
                )

                # Visualizza un'icona in base alla valutazione scelta
                selected_rating = st.session_state[f"rating_value_{query_id}"]
                rating_emoji = "😀" if selected_rating == "positive" else "😐"
                st.markdown(
                    f"<h1 style='text-align: center; color: {'green' if selected_rating == 'positive' else 'white' if not selected_rating else 'red'};'>{rating_emoji}</h1>", unsafe_allow_html=True)

            with col2:
                # Campo per il feedback
                feedback = st.text_area(
                    "Feedback (opzionale)",
                    value=st.session_state[f"rating_feedback_{query_id}"],
                    key=f"feedback_text_{query_id}",
                    height=100
                )

                # Pulsante di invio
                if st.button("Invia valutazione", key=f"submit_rating_{query_id}", use_container_width=True):
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
            cleaned_data = ResultVisualizer.clean_data_for_storage(data)

            return rating_manager.save_analysis_result(
                query_id=query_id,
                domanda=cleaned_data.get("domanda", ""),
                query_sql=cleaned_data.get("query_sql", ""),
                descrizione=cleaned_data.get("descrizione", ""),
                dati=cleaned_data.get("dati", ""),
                grafico_path="",
                llm_provider=cleaned_data.get("llm_provider"),
                cache_used=cleaned_data.get("cache_used", False),
                execution_time=cleaned_data.get("execution_time"),
                error=cleaned_data.get("error", None),
                error_traceback=cleaned_data.get("error_traceback", None)
            )
        except Exception as e:
            logger.error(f"Errore nel salvataggio del risultato: {e}")
            return False

    @staticmethod
    def clean_data_for_storage(data):
        """
        Pulisce i dati prima del salvataggio, rimuovendo elementi UI e limitando i dati.

        Args:
            data (dict): Dati originali da pulire

        Returns:
            dict: Dati puliti pronti per il salvataggio
        """
        # Crea una copia dei dati per non modificare l'originale
        cleaned_data = {}

        # Copia solo i campi che vogliamo salvare
        safe_keys = [
            "domanda", "query_sql", "descrizione", "dati", "grafici",
            "llm_provider", "cache_used", "execution_time",
            "error", "error_traceback", "attempts"
        ]

        for key in safe_keys:
            if key in data:
                # Per i dati, limitiamo a 1000 record per sicurezza
                if key == "dati" and data[key]:
                    cleaned_data[key] = data[key][:1000] if isinstance(
                        data[key], list) else data[key]
                else:
                    cleaned_data[key] = data[key]

        return cleaned_data
