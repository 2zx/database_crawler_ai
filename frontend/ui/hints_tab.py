"""
Gestisce l'interfaccia utente per la tab di gestione degli hint.
"""
import streamlit as st     # type: ignore
import pandas as pd     # type: ignore


class HintsTab:
    """Gestisce l'interfaccia per la tab di gestione hint."""

    def __init__(self, hint_manager):
        """
        Inizializza la tab di gestione hint.

        Args:
            hint_manager: Gestore degli hint
        """
        self.hint_manager = hint_manager

    def render(self):
        """Visualizza la tab di gestione degli hint."""
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

                st.dataframe(df_hints, hide_index=True)

                # Form per modificare o eliminare un hint
                st.subheader("Gestione degli hint esistenti")

                # Utilizziamo session_state per tenere traccia dell'hint selezionato
                if "selected_hint_id" not in st.session_state:
                    st.session_state.selected_hint_id = 0
                if "selected_hint_data" not in st.session_state:
                    st.session_state.selected_hint_data = None
                if "hint_action" not in st.session_state:
                    st.session_state.hint_action = "Modifica"

                # Funzione per caricare i dati dell'hint quando cambia l'ID
                def load_hint_data():
                    hint_id = st.session_state.hint_id_edit
                    if hint_id > 0:
                        hint_data = self.hint_manager.get_hint_by_id(hint_id)
                        if hint_data:
                            st.session_state.selected_hint_data = hint_data
                            st.session_state.selected_hint_id = hint_id
                        else:
                            st.warning(f"Hint con ID {hint_id} non trovato.")
                            st.session_state.selected_hint_data = None
                    else:
                        st.session_state.selected_hint_data = None

                # Contenitore per il feedback
                feedback_container = st.empty()

                col1, col2 = st.columns([1, 3])

                with col1:
                    # Utilizziamo key esplicite per evitare conflitti
                    hint_id_to_edit = st.number_input(
                        "ID Hint",
                        min_value=0,
                        step=1,
                        key="hint_id_edit",
                        on_change=load_hint_data
                    )

                with col2:
                    action = st.radio(
                        "Azione",
                        ["Modifica", "Attiva/Disattiva", "Elimina"],
                        key="hint_action",
                        on_change=lambda: setattr(st.session_state, 'hint_action', st.session_state.hint_action)
                    )

                # Mostriamo un'anteprima dell'hint selezionato
                if st.session_state.selected_hint_data:
                    hint_data = st.session_state.selected_hint_data

                    # Usiamo un expander per non prendere troppo spazio
                    with st.expander("Anteprima hint selezionato", expanded=True):
                        st.markdown(f"""
                        **ID**: {hint_data['id']}
                        **Categoria**: {hint_data['hint_category']}
                        **Stato**: {'✅ Attivo' if hint_data['active'] else '❌ Disattivato'}
                        **Testo**: {hint_data['hint_text']}
                        """)

                # Mostriamo campi differenti in base all'azione selezionata
                with st.form(key="edit_hint_form"):
                    if action == "Modifica":
                        # Preriempiamo i campi con i dati dell'hint selezionato
                        default_text = ""
                        default_category = ""

                        if st.session_state.selected_hint_data:
                            default_text = st.session_state.selected_hint_data["hint_text"]
                            default_category = st.session_state.selected_hint_data["hint_category"]

                        new_hint_text = st.text_area("Nuovo testo", key="new_hint_text", value=default_text)

                        # Ottieni le categorie disponibili
                        available_categories = self.hint_manager.get_all_categories()

                        # Trova l'indice della categoria corrente
                        default_category_index = 0
                        if default_category in available_categories:
                            default_category_index = available_categories.index(default_category)

                        new_hint_category = st.selectbox(
                            "Nuova categoria",
                            available_categories,
                            index=default_category_index,
                            key="new_hint_category"
                        )

                        update_button = st.form_submit_button("📝 Aggiorna hint")

                        if update_button and hint_id_to_edit > 0:
                            if self.hint_manager.update_hint(hint_id_to_edit, new_hint_text, new_hint_category):
                                feedback_container.success(f"✅ Hint {hint_id_to_edit} aggiornato con successo!")
                                # Ricarica i dati dell'hint
                                load_hint_data()
                            else:
                                feedback_container.error(f"❌ Errore nell'aggiornamento dell'hint {hint_id_to_edit}")

                    elif action == "Attiva/Disattiva":
                        # Mostriamo lo stato attuale dell'hint
                        current_status = ""
                        if st.session_state.selected_hint_data:
                            is_active = st.session_state.selected_hint_data["active"]
                            current_status = "✅ Attivo" if is_active else "❌ Disattivato"
                            st.write(f"Stato attuale: {current_status}")
                            st.write(f"Nuovo stato dopo il toggle: {'❌ Disattivato' if is_active else '✅ Attivo'}")

                        toggle_button = st.form_submit_button("🔄 Attiva/Disattiva hint")

                        if toggle_button and hint_id_to_edit > 0:
                            if self.hint_manager.toggle_hint_status(hint_id_to_edit):
                                feedback_container.success(f"✅ Stato dell'hint {hint_id_to_edit} modificato con successo!")
                                # Ricarica i dati dell'hint
                                load_hint_data()
                            else:
                                feedback_container.error(f"❌ Errore nella modifica dello stato dell'hint {hint_id_to_edit}")

                    elif action == "Elimina":
                        if st.session_state.selected_hint_data:
                            st.warning(f"""
                            ⚠️ Stai per eliminare definitivamente questo hint:

                            **ID**: {st.session_state.selected_hint_data['id']}
                            **Categoria**: {st.session_state.selected_hint_data['hint_category']}
                            **Testo**: {st.session_state.selected_hint_data['hint_text']}
                            """)
                        else:
                            st.warning("⚠️ Seleziona un hint da eliminare.")

                        delete_button = st.form_submit_button("🗑️ Elimina hint")

                        if delete_button and hint_id_to_edit > 0:
                            if self.hint_manager.delete_hint(hint_id_to_edit):
                                feedback_container.success(f"✅ Hint {hint_id_to_edit} eliminato con successo!")
                                # Resetta lo stato
                                st.session_state.selected_hint_data = None
                                st.session_state.selected_hint_id = 0
                            else:
                                feedback_container.error(f"❌ Errore nell'eliminazione dell'hint {hint_id_to_edit}")

            # Sezione per aggiungere un nuovo hint
            st.subheader("Aggiungi nuovo hint")

            with st.form(key="add_hint_form"):
                hint_text = st.text_area("Testo dell'hint", key="hint_text_input")

                # Ottieni le categorie dal backend
                hint_categories = self.hint_manager.get_all_categories()
                hint_category = st.selectbox("Categoria", hint_categories, key="hint_category_select")

                submit_button = st.form_submit_button("✅ Aggiungi hint")

                if submit_button and hint_text:
                    hint_id = self.hint_manager.add_hint(hint_text, hint_category)
                    if hint_id:
                        st.success(f"✅ Hint aggiunto con successo (ID: {hint_id})")
                        st.rerun()
                    else:
                        st.error("❌ Errore nell'aggiunta dell'hint")
