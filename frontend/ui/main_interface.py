"""
Gestisce l'interfaccia utente principale dell'applicazione.
"""
import streamlit as st  # type: ignore
from frontend.config import APP_TITLE, LLM_PROVIDERS


class UserInterface:
    """Gestisce l'interfaccia utente dell'applicazione."""

    def __init__(self, credentials_manager, llm_manager, hint_manager, backend_client):
        """
        Inizializza l'interfaccia utente.

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

        # Importiamo qui i moduli UI per evitare dipendenze circolari
        from frontend.ui.analysis_tab import AnalysisTab
        from frontend.ui.hints_tab import HintsTab
        from frontend.ui.config_tab import ConfigTab

        # Inizializziamo i tab
        self.analysis_tab = AnalysisTab(credentials_manager, llm_manager, hint_manager, backend_client)
        self.hints_tab = HintsTab(hint_manager)
        self.config_tab = ConfigTab(credentials_manager, llm_manager, hint_manager, backend_client)

    def render_sidebar(self):
        """Visualizza la sidebar con le impostazioni."""
        st.sidebar.title("Configurazione")

        # Tab per organizzare la sidebar
        tab1, tab2, tab3 = st.sidebar.tabs(["🧠 LLM", "🔐 Connessione", "💾 Cache"])

        with tab1:
            self.render_llm_settings()

        with tab2:
            self.render_connection_settings()

        with tab3:
            self.render_cache_settings()

    def render_llm_settings(self):
        """Visualizza le impostazioni del LLM nella sidebar."""

        # Selezione del provider LLM
        provider_options = [(key, value["name"]) for key, value in LLM_PROVIDERS.items()]
        selected_provider_index = 0

        # Trova l'indice del provider attualmente selezionato
        current_provider = self.credentials_manager.credentials.get("llm_provider", "openai")
        for i, (key, _) in enumerate(provider_options):
            if key == current_provider:
                selected_provider_index = i
                break

        selected_provider_name = st.selectbox(
            "Provider LLM",
            [name for _, name in provider_options],
            index=selected_provider_index
        )

        # Ottieni la chiave del provider selezionato
        selected_provider = next(key for key, value in LLM_PROVIDERS.items() if value["name"] == selected_provider_name)
        self.credentials_manager.credentials["llm_provider"] = selected_provider

        # Mostra i campi specifici per il provider
        provider_info = LLM_PROVIDERS[selected_provider]
        self.credentials_manager.credentials[provider_info["api_key_name"]] = st.text_input(
            f"Chiave API {provider_info['name']}",
            type="password",
            value=self.credentials_manager.credentials.get(provider_info["api_key_name"], "")
        )

        # Aggiungi il campo secret_key se richiesto dal provider
        if provider_info.get("requires_secret", False):
            self.credentials_manager.credentials[provider_info["secret_key_name"]] = st.text_input(
                f"Chiave Segreta {provider_info['name']}",
                type="password",
                value=self.credentials_manager.credentials.get(provider_info["secret_key_name"], "")
            )

        # Selezione del modello per il provider
        models = self.llm_manager.get_models_for_provider(selected_provider)
        model_options = [(model["id"], model["name"]) for model in models]

        if model_options:
            # Trova l'indice del modello attualmente selezionato
            current_model = self.credentials_manager.credentials.get(f"{selected_provider}_model", model_options[0][0])
            selected_model_index = 0
            for i, (model_id, _) in enumerate(model_options):
                if model_id == current_model:
                    selected_model_index = i
                    break

            selected_model_name = st.selectbox(
                f"Modello {provider_info['name']}",
                [name for _, name in model_options],
                index=selected_model_index
            )

            # Ottieni l'ID del modello selezionato
            selected_model = next(model_id for model_id, name in model_options if name == selected_model_name)
            self.credentials_manager.credentials[f"{selected_provider}_model"] = selected_model

        if st.button("💾 Salva configurazione"):
            self.credentials_manager.save_credentials()
            st.success("✅ Configurazione salvata con successo!")

    def render_connection_settings(self):
        """Visualizza le impostazioni di connessione nella sidebar."""
        from frontend.utils.connection_profiles import ConnectionProfileManager
        from frontend.config import PROFILES_FILE

        profile_manager = ConnectionProfileManager(PROFILES_FILE)

        # Sezione Profili di connessione (NUOVA)
        st.subheader("💼 Profili di connessione")

        # Ottieni i profili disponibili
        profile_names = profile_manager.get_profile_names()

        # Selettore di profili
        if profile_names:
            profiles_options = ["---"] + profile_names
            selected_profile = st.selectbox(
                "Seleziona un profilo",
                options=profiles_options,
                key="profile_selector"
            )

            col0, col1, col2 = st.columns(3)
            # Se viene selezionato un profilo, caricalo
            if selected_profile != "---":
                with col0:
                    if st.button("📂 Carica profilo", key="load_profile_button"):
                        profile_data = profile_manager.get_profile(selected_profile)
                        if profile_data:
                            # Aggiorna le credenziali con quelle del profilo
                            for key, value in profile_data.items():
                                self.credentials_manager.credentials[key] = value

                            # Salva le credenziali aggiornate
                            self.credentials_manager.save_credentials()
                            st.success(f"✅ Profilo '{selected_profile}' caricato con successo!")
                            st.rerun()
                        else:
                            st.error(f"❌ Errore nel caricamento del profilo '{selected_profile}'")

                with col1:
                    if st.button("🗑️ Elimina", key="delete_profile_button"):
                        if selected_profile != "---":
                            if profile_manager.delete_profile(selected_profile):
                                st.success(f"✅ Profilo '{selected_profile}' eliminato con successo!")
                                st.rerun()
                            else:
                                st.error(f"❌ Errore nell'eliminazione del profilo '{selected_profile}'")
                        else:
                            st.warning("⚠️ Seleziona un profilo da eliminare")

                with col2:
                    if st.button("🔄 Aggiorna", key="update_profile_button"):
                        if selected_profile != "---":
                            # Salva le credenziali correnti nel profilo selezionato
                            if profile_manager.save_profile(selected_profile, self.credentials_manager.credentials):
                                st.success(f"✅ Profilo '{selected_profile}' aggiornato con successo!")
                            else:
                                st.error(f"❌ Errore nell'aggiornamento del profilo '{selected_profile}'")
                        else:
                            st.warning("⚠️ Seleziona un profilo da aggiornare")

        # Salva il profilo corrente
        with st.form(key="save_profile_form"):
            profile_name = st.text_input("Nome del nuovo profilo", key="new_profile_name")
            save_button = st.form_submit_button("💾 Salva come nuovo profilo")

            if save_button and profile_name:
                # Verifica se il profilo esiste già
                if profile_name in profile_names:
                    if st.warning(f"⚠️ Il profilo '{profile_name}' esiste già. Vuoi sovrascriverlo?"):
                        st.button("✓ Sì, sovrascrivi", key="overwrite_confirm", on_click=lambda: self._save_profile(profile_name))
                        st.button("✗ No, annulla", key="overwrite_cancel")
                else:
                    # Salva il nuovo profilo
                    if profile_manager.save_profile(profile_name, self.credentials_manager.credentials):
                        st.success(f"✅ Nuovo profilo '{profile_name}' salvato con successo!")
                        st.rerun()
                    else:
                        st.error(f"❌ Errore nel salvataggio del profilo '{profile_name}'")

        st.markdown("---")  # Separatore visivo

        # Sezione SSH
        st.subheader("🔐 SSH")

        use_ssh = st.checkbox("Usa connessione SSH (tunnel)",
                              value=bool(self.credentials_manager.credentials.get("ssh_host", "")))
        self.credentials_manager.credentials["use_ssh"] = use_ssh

        if use_ssh:
            self.credentials_manager.credentials["ssh_host"] = st.text_input(
                "IP Server SSH",
                value=self.credentials_manager.credentials.get("ssh_host", "192.168.1.100")
            )
            self.credentials_manager.credentials["ssh_user"] = st.text_input(
                "Utente SSH",
                value=self.credentials_manager.credentials.get("ssh_user", "ubuntu")
            )
            self.credentials_manager.credentials["ssh_key"] = st.text_area(
                "Chiave Privata SSH",
                value=self.credentials_manager.credentials.get("ssh_key", "")
            )
        else:
            # Se SSH non è usato, svuota i campi
            self.credentials_manager.credentials["ssh_host"] = ""
            self.credentials_manager.credentials["ssh_user"] = ""
            self.credentials_manager.credentials["ssh_key"] = ""

        # Sezione Database
        st.subheader("🗄️ Database")

        # Selezione del tipo di database
        db_options = ["PostgreSQL", "SQL Server"]
        current_db_type = self.credentials_manager.credentials.get("db_type", "postgresql")
        default_index = 0 if current_db_type == "postgresql" else 1

        selected_db_type = st.selectbox(
            "Tipo di Database",
            db_options,
            index=default_index
        )

        # Mappa il valore selezionato al valore interno
        self.credentials_manager.credentials["db_type"] = "postgresql" if selected_db_type == "PostgreSQL" else "sqlserver"

        # Testo descrittivo basato sul tipo selezionato
        db_type_label = "PostgreSQL" if selected_db_type == "PostgreSQL" else "SQL Server"
        default_port = "5432" if selected_db_type == "PostgreSQL" else "1433"
        default_user = "postgres" if selected_db_type == "PostgreSQL" else "sa"

        self.credentials_manager.credentials["db_host"] = st.text_input(
            f"Host {db_type_label}",
            value=self.credentials_manager.credentials.get("db_host", "127.0.0.1")
        )
        self.credentials_manager.credentials["db_port"] = st.text_input(
            f"Porta {db_type_label}",
            value=self.credentials_manager.credentials.get("db_port", default_port)
        )
        self.credentials_manager.credentials["db_user"] = st.text_input(
            "Utente Database",
            value=self.credentials_manager.credentials.get("db_user", default_user)
        )
        self.credentials_manager.credentials["db_password"] = st.text_input(
            "Password Database",
            type="password",
            value=self.credentials_manager.credentials.get("db_password", "")
        )
        self.credentials_manager.credentials["db_name"] = st.text_input(
            "Nome Database",
            value=self.credentials_manager.credentials.get("db_name", "mio_database")
        )

        # Ottieni le categorie disponibili
        available_categories = self.hint_manager.get_all_categories()
        current_hint_category = self.credentials_manager.credentials.get("hint_category", "generale")

        # Trova l'indice della categoria corrente
        default_category_index = 0
        if current_hint_category in available_categories:
            default_category_index = available_categories.index(current_hint_category)

        self.credentials_manager.credentials["hint_category"] = st.selectbox(
            "Categoria hint",
            available_categories,
            index=default_category_index,
            key="config_hint_category"
        )

        # Layout dei pulsanti finali: barra separatrice
        st.markdown("---")

        # Pulsante di test e di salvataggio su due colonne
        col1, col2 = st.columns(2)

        with col1:
            if st.button("🔌 Test connessione", use_container_width=True):
                self.test_connection()

        with col2:
            if st.button("💾 Salva credenziali", use_container_width=True):
                self.credentials_manager.save_credentials()
                st.success("✅ Credenziali salvate con successo!")

        # Aggiungiamo la logica per mostrare feedback dettagliato del test di connessione
        if "test_result" in st.session_state:
            result = st.session_state.test_result
            if result.get("ssh_success") and result.get("db_success"):
                st.success("✅ Connessione completata con successo!")
            else:
                if not result.get("ssh_success"):
                    st.error(f"❌ Errore SSH: {result.get('ssh_error', 'Errore sconosciuto')}")
                elif not result.get("db_success"):
                    st.warning(f"⚠️ SSH OK, ma errore database: {result.get('db_error', 'Errore sconosciuto')}")

                # Suggerimenti per risolvere problemi comuni
                with st.expander("🔧 Suggerimenti per risolvere i problemi"):
                    st.markdown("""
                    ### Problemi di connessione SSH
                    - Verifica che l'indirizzo IP e la porta del server SSH siano corretti
                    - Controlla che l'utente SSH abbia i permessi di accesso
                    - Assicurati che la chiave privata SSH sia nel formato corretto
                    - Verifica che il server SSH sia raggiungibile dalla tua rete

                    ### Problemi di connessione al database
                    - Verifica che il nome utente e la password del database siano corretti
                    - Controlla che il nome del database sia scritto correttamente
                    - Assicurati che l'utente abbia i permessi per accedere al database
                    - Verifica che il firewall del server non blocchi la connessione
                    - Se usi SSH, controlla che l'utente SSH possa raggiungere il server database
                    """)

    def render_cache_settings(self):
        """Visualizza le impostazioni della cache nella sidebar."""

        if st.button("🔄 Esporta Hint"):
            if self.hint_manager.export_hints():
                st.success("✅ Hint esportati con successo!")
            else:
                st.error("❌ Errore nell'esportazione degli hint")

        if st.button("📥 Importa Hint"):
            if self.hint_manager.import_hints():
                st.success("✅ Hint importati con successo!")
            else:
                st.error("❌ Errore nell'importazione degli hint")

    def render_main_interface(self):
        """Visualizza l'interfaccia principale dell'applicazione."""

        # Aggiungi il logo sopra il titolo
        cola, colb = st.columns([1, 2])
        with cola:
            st.image("/app/frontend/static/laundrybot_jit40.png", width=300)
        with colb:
            st.title(APP_TITLE)

        st.write("")
        st.write("")

        # Creiamo i tabs per le diverse sezioni
        tab1, tab2, tab3 = st.tabs(["📊 Analisi Dati", "✏️ Hint Interpretazione", "⚙️ Configurazioni"])

        # Renderizza i contenuti nei diversi tab
        with tab1:
            action_data = self.analysis_tab.render()

        with tab2:
            self.hints_tab.render()

        with tab3:
            self.config_tab.render()

        # Ritorna il valore dell'azione dall'analysis_tab
        return action_data

    def test_connection(self):
        """
        Testa la connessione SSH e SQL con le credenziali correnti.
        """
        with st.spinner("Test in corso..."):
            try:
                # Prepara le configurazioni
                ssh_config = self.credentials_manager.get_ssh_config()
                db_config = self.credentials_manager.get_db_config()

                # Effettua il test attraverso l'API
                response = self.backend_client.test_connection(ssh_config, db_config)

                if response.status_code == 200:
                    result = response.json()
                    st.session_state.test_result = result

                    if result.get("ssh_success") and result.get("db_success"):
                        st.success("✅ Connessione SSH e database riuscita!")
                    elif result.get("ssh_success"):
                        st.warning(
                            "⚠️ Connessione SSH riuscita, ma la connessione al database è fallita: " + result.get(
                                "db_error", ""
                            )
                        )
                    else:
                        st.error("❌ Connessione SSH fallita: " + result.get("ssh_error", ""))
                else:
                    st.error(f"❌ Errore durante il test: {response.text}")
            except Exception as e:
                st.error(f"❌ Errore di comunicazione: {str(e)}")
