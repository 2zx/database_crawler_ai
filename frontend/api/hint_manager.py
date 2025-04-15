"""
Gestisce gli hint per l'interpretazione dei dati.
Questo modulo si interfaccia con il backend per gestire gli hint che guidano l'AI
nell'interpretazione dei dati.
"""
import requests     # type: ignore
import streamlit as st      # type: ignore


class HintManager:
    """Gestisce gli hint per l'interpretazione dei dati."""

    def __init__(self, backend_url):
        """
        Inizializza il gestore degli hint.

        Args:
            backend_url (str): URL dell'API backend
        """
        self.backend_url = backend_url

    def get_hint_by_id(self, hint_id):
        """
        Recupera un hint specifico tramite il suo ID.

        Args:
            hint_id (int): ID dell'hint da recuperare

        Returns:
            dict or None: Dati dell'hint o None se non trovato
        """
        try:
            response = requests.get(f"{self.backend_url}/hints/{hint_id}")
            if response.status_code == 200:
                return response.json()
            else:
                st.warning(f"Errore nel recupero dell'hint con ID {hint_id}: {response.text}")
                return None
        except Exception as e:
            st.warning(f"Errore nel recupero dell'hint: {e}")
            return None

    def get_all_hints(self):
        """
        Recupera tutti gli hint dal backend.

        Returns:
            list: Lista di tutti gli hint
        """
        try:
            response = requests.get(f"{self.backend_url}/hints")
            if response.status_code == 200:
                return response.json()
            else:
                st.warning("Non è stato possibile recuperare gli hint.")
                return []
        except Exception as e:
            st.warning(f"Errore nel recupero degli hint: {e}")
            return []

    def get_active_hints(self, hint_category=""):
        """
        Recupera solo gli hint attivi dal backend.

        Args:
            hint_category (str): Filtra per categoria (opzionale)

        Returns:
            list: Lista degli hint attivi
        """
        try:
            response = requests.get(f"{self.backend_url}/hints/active?hint_category={hint_category}")
            if response.status_code == 200:
                return response.json()
            else:
                st.warning("Non è stato possibile recuperare gli hint attivi.")
                return []
        except Exception as e:
            st.warning(f"Errore nel recupero degli hint attivi: {e}")
            return []

    def add_hint(self, hint_text, hint_category="generale"):
        """
        Aggiunge un nuovo hint.

        Args:
            hint_text (str): Il testo dell'hint
            hint_category (str): La categoria dell'hint

        Returns:
            int or None: ID dell'hint aggiunto o None in caso di errore
        """
        try:
            response = requests.post(
                f"{self.backend_url}/hints",
                json={"hint_text": hint_text, "hint_category": hint_category}
            )
            if response.status_code == 200:
                return response.json().get("id")
            else:
                st.warning(f"Errore nell'aggiunta dell'hint: {response.text}")
                return None
        except Exception as e:
            st.warning(f"Errore nell'aggiunta dell'hint: {e}")
            return None

    def update_hint(self, hint_id, hint_text=None, hint_category=None, active=None):
        """
        Aggiorna un hint esistente.

        Args:
            hint_id (int): ID dell'hint da aggiornare
            hint_text (str, optional): Nuovo testo
            hint_category (str, optional): Nuova categoria
            active (int, optional): Nuovo stato (1=attivo, 0=disattivo)

        Returns:
            bool: True se l'aggiornamento è riuscito, False altrimenti
        """
        try:
            payload = {}
            if hint_text is not None:
                payload["hint_text"] = hint_text
            if hint_category is not None:
                payload["hint_category"] = hint_category
            if active is not None:
                payload["active"] = active

            response = requests.put(
                f"{self.backend_url}/hints/{hint_id}",
                json=payload
            )

            if response.status_code == 200:
                return True
            else:
                st.warning(f"Errore nell'aggiornamento dell'hint: {response.text}")
                return False
        except Exception as e:
            st.warning(f"Errore nell'aggiornamento dell'hint: {e}")
            return False

    def delete_hint(self, hint_id):
        """
        Elimina un hint.

        Args:
            hint_id (int): ID dell'hint da eliminare

        Returns:
            bool: True se l'eliminazione è riuscita, False altrimenti
        """
        try:
            response = requests.delete(f"{self.backend_url}/hints/{hint_id}")
            if response.status_code == 200:
                return True
            else:
                st.warning(f"Errore nell'eliminazione dell'hint: {response.text}")
                return False
        except Exception as e:
            st.warning(f"Errore nell'eliminazione dell'hint: {e}")
            return False

    def toggle_hint_status(self, hint_id):
        """
        Attiva o disattiva un hint.

        Args:
            hint_id (int): ID dell'hint di cui cambiare lo stato

        Returns:
            bool: True se l'operazione è riuscita, False altrimenti
        """
        try:
            response = requests.put(f"{self.backend_url}/hints/{hint_id}/toggle")
            if response.status_code == 200:
                return True
            else:
                st.warning(f"Errore nel cambio di stato dell'hint: {response.text}")
                return False
        except Exception as e:
            st.warning(f"Errore nel cambio di stato dell'hint: {e}")
            return False

    def get_all_categories(self):
        """
        Recupera tutte le categorie dal backend.

        Returns:
            list: Lista di nomi delle categorie
        """
        try:
            response = requests.get(f"{self.backend_url}/categories")
            if response.status_code == 200:
                return response.json().get("categories", [])
            else:
                st.warning("Non è stato possibile recuperare le categorie.")
                return []
        except Exception as e:
            st.warning(f"Errore nel recupero delle categorie: {e}")
            return []

    def add_category(self, category_name):
        """
        Aggiunge una nuova categoria.

        Args:
            category_name (str): Nome della nuova categoria

        Returns:
            bool: True se l'aggiunta è riuscita, False altrimenti
        """
        try:
            response = requests.post(
                f"{self.backend_url}/categories",
                json={"name": category_name}
            )
            if response.status_code == 200:
                return True
            else:
                st.warning(f"Errore nell'aggiunta della categoria: {response.text}")
                return False
        except Exception as e:
            st.warning(f"Errore nell'aggiunta della categoria: {e}")
            return False

    def delete_category(self, category_name, replace_with="generale"):
        """
        Elimina una categoria.

        Args:
            category_name (str): Nome della categoria da eliminare
            replace_with (str): Nome della categoria con cui sostituire

        Returns:
            bool: True se l'eliminazione è riuscita, False altrimenti
        """
        try:
            response = requests.delete(
                f"{self.backend_url}/categories",
                json={"name": category_name, "replace_with": replace_with}
            )
            if response.status_code == 200:
                return True
            else:
                st.warning(f"Errore nell'eliminazione della categoria: {response.text}")
                return False
        except Exception as e:
            st.warning(f"Errore nell'eliminazione della categoria: {e}")
            return False

    def export_hints(self):
        """
        Esporta gli hint in un file JSON.

        Returns:
            bool: True se l'esportazione è riuscita, False altrimenti
        """
        try:
            response = requests.post(f"{self.backend_url}/hints/export")
            if response.status_code == 200:
                return True
            else:
                st.warning(f"Errore nell'esportazione degli hint: {response.text}")
                return False
        except Exception as e:
            st.warning(f"Errore nell'esportazione degli hint: {e}")
            return False

    def import_hints(self):
        """
        Importa gli hint da un file JSON.

        Returns:
            bool: True se l'importazione è riuscita, False altrimenti
        """
        try:
            response = requests.post(f"{self.backend_url}/hints/import")
            if response.status_code == 200:
                return True
            else:
                st.warning(f"Errore nell'importazione degli hint: {response.text}")
                return False
        except Exception as e:
            st.warning(f"Errore nell'importazione degli hint: {e}")
            return False
