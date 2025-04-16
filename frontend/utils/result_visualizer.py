"""
Gestisce la visualizzazione dei risultati dell'analisi.
"""
import pandas as pd     # type: ignore
import streamlit as st      # type: ignore
from io import BytesIO
from frontend.config import LLM_PROVIDERS


class ResultVisualizer:
    """Gestisce la visualizzazione dei risultati dell'analisi."""

    @staticmethod
    def display_results(data):
        """
        Visualizza i risultati dell'analisi.

        Args:
            data (dict): Dati risultanti dall'analisi
        """
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

        # Mostra domande correlate (se disponibili)
        if "related_questions" in data and data["related_questions"]:
            st.subheader("🔄 Possibili approfondimenti:")

            for i, question in enumerate(data["related_questions"]):
                col1, col2 = st.columns([9, 1])
                with col1:
                    st.write(f"{i+1}. {question}")
                with col2:
                    # Usiamo un key univoco per ogni bottone
                    button_key = f"explore_{i}_{hash(question)}"
                    if st.button("🔍", key=button_key):
                        # Imposta direttamente la domanda
                        st.session_state.domanda_corrente = question
                        # Forza rerun per applicare immediatamente le modifiche
                        st.rerun()
