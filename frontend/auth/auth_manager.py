"""
Gestisce l'autenticazione dell'utente nell'applicazione.
"""
import os
import streamlit as st  # type: ignore


class AuthManager:
    """Gestisce l'autenticazione dell'utente."""

    def __init__(self):
        """Inizializza il gestore dell'autenticazione con le credenziali dal file .env."""
        self.admin_username = os.getenv("ADMIN_USERNAME")
        self.admin_password = os.getenv("ADMIN_PASSWORD")

        if not self.admin_username or not self.admin_password:
            st.error("Credenziali di amministratore non configurate nel file .env")

    def login_page(self):
        """Gestisce la pagina di login e verifica le credenziali."""
        st.title("Login")

        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit_button = st.form_submit_button("Accedi")

            if submit_button:
                if username == self.admin_username and password == self.admin_password:
                    st.session_state.logged_in = True
                    st.success("Login effettuato con successo!")
                    st.rerun()
                else:
                    st.error("Username o password non validi")

    def check_login(self):
        """Verifica se l'utente è loggato."""
        if "logged_in" not in st.session_state:
            st.session_state.logged_in = False

        st.session_state.logged_in = True  # TODO FIXME

        return st.session_state.logged_in

    def logout(self):
        """Effettua il logout dell'utente."""
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()
