"""
Gestisce l'interfaccia utente per la tab di storico delle analisi.
"""
import streamlit as st  # type: ignore
import pandas as pd  # type: ignore
from datetime import datetime
from frontend.utils import ResultVisualizer


class HistoryTab:
    """Gestisce l'interfaccia per la tab dello storico delle analisi."""

    def __init__(self, rating_manager):
        """
        Inizializza la tab dello storico.

        Args:
            rating_manager: Gestore delle valutazioni e dello storico
        """
        self.rating_manager = rating_manager

    def render(self):
        """Visualizza la tab dello storico delle analisi."""
        # Assicuriamoci che il contenuto sia visibile
        st.header("📚 Storico Analisi")

        # Recupera le statistiche generali
        stats = self.rating_manager.get_ratings_stats()

        # Visualizza le statistiche in card
        cols = st.columns(4)
        with cols[0]:
            st.metric("Totale Analisi", stats["total"])
        with cols[1]:
            st.metric("Valutazioni Positive", stats["positive"])
        with cols[2]:
            st.metric("Valutazioni Negative", stats["negative"])
        with cols[3]:
            st.metric("% Positiva", f"{stats['positive_percentage']:.1f}%")

        # Aggiungiamo un container per garantire che il contenuto sia visibile
        history_container = st.container()

        with history_container:
            # Filtri e paginazione
            col1, col2 = st.columns([3, 1])

            with col1:
                search_query = st.text_input("🔍 Cerca nelle domande", "")

            with col2:
                page_size = st.selectbox("Elementi per pagina", [
                                         10, 25, 50, 100], index=0)

            # Inizializza lo stato per la paginazione
            if "history_page" not in st.session_state:
                st.session_state.history_page = 0

            # Calcola l'offset in base alla pagina corrente
            offset = st.session_state.history_page * page_size

            # Recupera i risultati delle analisi
            results = self.rating_manager.get_all_analysis_results(
                limit=page_size, offset=offset)

            # Filtra i risultati in base alla ricerca (lato client)
            if search_query:
                results = [r for r in results if search_query.lower()
                           in r.get("domanda", "").lower()]

            # Visualizza i risultati in una tabella
            if results:
                # Converti risultati in DataFrame per visualizzazione
                df_results = pd.DataFrame(results)

                # Formatta i timestamp
                if "timestamp" in df_results.columns:
                    df_results["timestamp"] = df_results["timestamp"].apply(
                        lambda ts: datetime.fromisoformat(
                            ts).strftime("%d/%m/%Y %H:%M")
                    )

                # Rinomina le colonne per una migliore visualizzazione
                df_results = df_results.rename(columns={
                    "query_id": "ID Query",
                    "domanda": "Domanda",
                    "timestamp": "Data/Ora",
                    "llm_provider": "LLM",
                    "cache_used": "Cache"
                })

                # Visualizza la tabella con i risultati
                st.dataframe(
                    df_results[["Data/Ora", "Domanda", "LLM", "Cache"]],
                    height=400,
                    use_container_width=True
                )

                # Pulsanti per la paginazione
                col1, col2, col3 = st.columns([1, 3, 1])

                with col1:
                    if st.session_state.history_page > 0:
                        if st.button("⬅️ Precedente"):
                            st.session_state.history_page -= 1
                            st.rerun()

                with col2:
                    st.write(f"Pagina {st.session_state.history_page + 1}")

                with col3:
                    if len(results) == page_size:  # Ci sono probabilmente altre pagine
                        if st.button("Successiva ➡️"):
                            st.session_state.history_page += 1
                            st.rerun()

                # Dettaglio di un'analisi specifica
                st.subheader("Dettaglio Analisi")

                # Selezione dell'analisi da visualizzare
                selected_query_id = st.selectbox(
                    "Seleziona un'analisi per visualizzare i dettagli:",
                    options=[r["query_id"] for r in results],
                    format_func=lambda qid: next(
                        (r["domanda"] for r in results if r["query_id"] == qid), qid)
                )

                if selected_query_id:
                    # Recupera i dettagli dell'analisi selezionata
                    analysis_details = self.rating_manager.get_analysis_result(
                        selected_query_id)

                    if analysis_details:
                        # Recupera la valutazione se esistente
                        rating = self.rating_manager.get_rating(
                            selected_query_id)

                        # Visualizza i dettagli dell'analisi
                        with st.expander("Dettagli Query", expanded=True):
                            st.markdown(
                                f"**Domanda**: {analysis_details.get('domanda', '')}")
                            st.markdown(
                                f"**Data**: {datetime.fromisoformat(analysis_details.get('timestamp', '')).strftime('%d/%m/%Y %H:%M')}")
                            st.markdown(
                                f"**LLM**: {analysis_details.get('llm_provider', 'N/A')}")
                            st.markdown(
                                f"**Cache**: {'Sì' if analysis_details.get('cache_used', False) else 'No'}")

                            if analysis_details.get('execution_time'):
                                st.markdown(
                                    f"**Tempo di esecuzione**: {analysis_details.get('execution_time')} ms")

                            st.code(analysis_details.get(
                                'query_sql', ''), language="sql")

                        # Visualizza l'analisi dei risultati
                        ResultVisualizer.display_results({
                            "descrizione": analysis_details.get('descrizione', ''),
                            "dati": analysis_details.get('dati', []),
                            "query_sql": analysis_details.get('query_sql', ''),
                            "grafici": analysis_details.get('grafico_path'),
                            "llm_provider": analysis_details.get('llm_provider'),
                            "cache_used": analysis_details.get('cache_used', False)
                        })

                        # Mostra la valutazione se esistente
                        if rating:
                            st.subheader("Valutazione")
                            st.markdown(
                                f"**Valutazione**: {'👍 Positiva' if rating.get('positive', False) else '👎 Negativa'}")
                            if rating.get('feedback'):
                                st.markdown(
                                    f"**Feedback**: {rating.get('feedback', '')}")
                        else:
                            st.info(
                                "Nessuna valutazione disponibile per questa analisi.")
                    else:
                        st.warning(
                            "Impossibile recuperare i dettagli dell'analisi selezionata.")
            else:
                st.info("Nessun risultato di analisi trovato.")
