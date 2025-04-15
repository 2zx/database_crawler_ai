"""
Gestisce l'interfaccia utente per la tab di configurazione.
"""
import streamlit as st      # type: ignore


class ConfigTab:
    """Gestisce l'interfaccia per la tab di configurazione."""

    def __init__(self, credentials_manager, llm_manager, hint_manager, backend_client):
        """
        Inizializza la tab di configurazione.

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
        """Visualizza la tab di configurazione."""
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

            st.subheader("Schema Database")

            # Inizializzazione dello stato del pulsante
            if "refresh_clicked" not in st.session_state:
                st.session_state.refresh_clicked = False

            # Callback quando viene premuto il bottone Riscansiona
            def on_refresh_click():
                st.session_state.refresh_clicked = True

            if st.button(
                "🔄 Riscansiona Database",
                use_container_width=True,
                disabled=st.session_state.get("query_in_progress", False),
                on_click=on_refresh_click
            ):
                pass  # L'azione viene gestita nel callback
