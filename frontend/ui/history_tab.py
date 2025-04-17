"""
Gestisce l'interfaccia utente per la tab di storico delle analisi.
"""
import streamlit as st  # type: ignore
import pandas as pd  # type: ignore
from datetime import datetime


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

        # Recupera le statistiche generali complete
        stats = self.rating_manager.get_all_analysis_stats()

        # Visualizza le statistiche principali
        st.subheader("📊 Statistiche generali")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Totale Analisi", stats["total"])
        with col2:
            st.metric("Analisi con Cache", f"{stats['cached']} ({stats['cache_percentage']:.1f}%)")
        with col3:
            st.metric("Con Errore", f"{stats['with_errors']} ({stats['error_percentage']:.1f}%)")
        with col4:
            st.metric("Valutate", f"{stats['rated']} ({stats['rated_percentage']:.1f}%)")

        # Visualizza le statistiche delle valutazioni
        st.subheader("⭐ Statistiche valutazioni")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            # Valutazioni positive sul totale delle analisi
            positive_total_percentage = (stats['positive'] / stats['total'] * 100) if stats['total'] > 0 else 0
            st.metric("Valutazioni Positive sul totale", f"{stats['positive']} ({positive_total_percentage:.1f}%)")
        with col2:
            # Valutazioni negative sul totale delle analisi
            negative_total_percentage = (stats['negative'] / stats['total'] * 100) if stats['total'] > 0 else 0
            st.metric("Valutazioni Negative sul totale", f"{stats['negative']} ({negative_total_percentage:.1f}%)")
        with col3:
            # Percentuale di valutazioni positive sulle analisi valutate
            st.metric("% Valutazioni Positive", f"{stats['positive_percentage']:.1f}%")
        with col4:
            # Percentuale di valutazioni negative sulle analisi valutate
            st.metric("% Valutazioni Negative", f"{(100 - stats['positive_percentage']):.1f}%")

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

            # Visualizza i risultati in una tabella interattiva
            if results:
                # Visualizza la tabella con i risultati in modo interattivo
                if "selected_analysis" in st.query_params:
                    selected_query_id = st.query_params["selected_analysis"]
                else:
                    selected_query_id = None

                # Converti risultati in DataFrame per visualizzazione
                df_results = pd.DataFrame(results)

                # Formatta i timestamp
                if "timestamp" in df_results.columns:
                    df_results["timestamp"] = df_results["timestamp"].apply(
                        lambda ts: datetime.fromisoformat(ts).strftime("%d/%m/%Y %H:%M")
                    )

                # Rinomina le colonne per una migliore visualizzazione
                df_display = df_results.rename(columns={
                    "query_id": "ID Query",
                    "domanda": "Domanda",
                    "timestamp": "Data/Ora",
                    "llm_provider": "LLM",
                    "cache_used": "Cache"
                })

                # Selettore degli elementi con una tecnica diversa
                row_clicked = False
                for i, row in df_display.iterrows():
                    cols = st.columns([3, 10, 2, 1, 1])

                    with cols[0]:
                        st.text(row["Data/Ora"])
                    with cols[1]:
                        st.text(row["Domanda"][:80] + ("..." if len(row["Domanda"]) > 80 else ""))
                    with cols[2]:
                        st.text(row["LLM"] if row["LLM"] else "N/A")
                    with cols[3]:
                        st.text("✓" if row["Cache"] else "✗")
                    with cols[4]:
                        if st.button("🔍", key=f"view_{i}"):
                            selected_query_id = results[i]["query_id"]
                            st.query_params["selected_analysis"] = selected_query_id
                            row_clicked = True

                    # Aggiungi una linea sottile tra le righe
                    st.markdown(
                        '<hr style="margin-top: 0; margin-bottom: 0; height: 1px; border: none; background-color: #f0f0f0;">',
                        unsafe_allow_html=True
                    )

                if row_clicked:
                    st.rerun()

                # Pulsanti per la paginazione
                col1, col2, col3 = st.columns([1, 3, 1])

                with col1:
                    if st.session_state.history_page > 0:
                        if st.button("⬅️ Precedente"):
                            st.session_state.history_page -= 1
                            st.query_params.clear()
                            st.rerun()

                with col2:
                    st.write(f"Pagina {st.session_state.history_page + 1}")

                with col3:
                    if len(results) == page_size:  # Ci sono probabilmente altre pagine
                        if st.button("Successiva ➡️"):
                            st.session_state.history_page += 1
                            st.query_params.clear()
                            st.rerun()

                # Visualizziamo i dettagli se abbiamo un query_id selezionato
                if selected_query_id:
                    with st.spinner("Caricamento dettagli analisi..."):
                        # Recupera i dettagli dell'analisi selezionata
                        analysis_details = self.rating_manager.get_analysis_result(selected_query_id)

                        if analysis_details:
                            # Recupera la valutazione se esistente
                            rating = self.rating_manager.get_rating(selected_query_id)

                            if not rating:
                                rating = {
                                    "positive": False,
                                    "feedback": None
                                }

                            st.divider()

                            # Visualizza i dettagli dell'analisi
                            st.subheader(f"Domanda: {analysis_details.get('domanda', '')}")

                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.info(f"**Data**: {datetime.fromisoformat(analysis_details.get('timestamp', '')).strftime('%d/%m/%Y %H:%M')}")
                            with col2:
                                st.info(f"**LLM**: {analysis_details.get('llm_provider', 'N/A')}")
                            with col3:
                                st.info(f"**Cache**: {'Sì ✓' if analysis_details.get('cache_used', False) else 'No ✗'}")
                            with col4:
                                st.info(f"**Rating**: {'👍' if rating.get('positive', False) else '👎'}")

                            if analysis_details.get('execution_time'):
                                st.caption(f"Tempo di esecuzione: {analysis_details.get('execution_time')} ms")

                            # Mostra se ci sono stati errori
                            if analysis_details.get('error'):
                                st.error(f"**Errore**: {analysis_details.get('error', '')}")
                                with st.expander("Dettagli errore"):
                                    st.code(analysis_details.get('error_traceback', ''))

                            # Mostra la query SQL se presente
                            if analysis_details.get('query_sql'):
                                with st.expander("Query SQL", expanded=False):
                                    st.code(analysis_details.get('query_sql', ''), language="sql")

                            # Visualizza i dati dell'analisi solo se non ci sono errori o se ci sono dati nonostante l'errore
                            has_data = len(analysis_details.get('dati', [])) > 0

                            if not analysis_details.get('error') or has_data:
                                # Crea un DataFrame dai dati
                                if has_data:
                                    df = pd.DataFrame(analysis_details.get('dati', []))
                                    st.subheader("📋 Dati dell'analisi:")
                                    st.dataframe(df, height=300, hide_index=True)

                            # Visualizza la descrizione
                            if analysis_details.get('descrizione'):
                                st.subheader("📝 Descrizione")
                                st.write(analysis_details.get('descrizione', ''))

                            # Mostra la valutazione se esistente
                            if rating:
                                st.subheader("⭐ Dettagli valutazione")
                                sentiment = "positiva" if rating.get('positive', False) else "negativa"
                                emoji = "👍" if rating.get('positive', False) else "👎"
                                st.success(f"{emoji} Valutazione {sentiment}") if rating.get('positive', False) else st.error(f"{emoji} Valutazione {sentiment}")
                                if rating.get('feedback'):
                                    st.info(f"**Feedback**: {rating.get('feedback', '')}")
                            else:
                                st.info("Nessuna valutazione disponibile per questa analisi.")
                        else:
                            st.warning("Impossibile recuperare i dettagli dell'analisi selezionata.")

            else:
                st.info("Nessun risultato di analisi trovato.")
