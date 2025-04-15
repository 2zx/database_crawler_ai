"""
Gestisce le configurazioni e le operazioni relative ai modelli di linguaggio (LLM).
"""
import requests  # type: ignore
import streamlit as st  # type: ignore


class LLMManager:
    """Gestisce le configurazioni e le operazioni relative ai LLM."""

    def __init__(self, backend_url):
        """
        Inizializza il gestore LLM.

        Args:
            backend_url (str): URL dell'API backend
        """
        self.backend_url = backend_url
        self.available_models = self.fetch_available_models()

    def fetch_available_models(self):
        """
        Recupera l'elenco dei modelli disponibili dal backend.

        Returns:
            dict: Dizionario dei modelli disponibili per provider
        """
        try:
            response = requests.get(f"{self.backend_url}/available_models")
            if response.status_code == 200:
                return response.json()
            else:
                st.warning("Non è stato possibile recuperare l'elenco dei modelli. Usando valori predefiniti.")
                return {
                    "openai": [{"id": "gpt-4o-mini", "name": "GPT-4o Mini"}],
                    "claude": [{"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku"}],
                    "deepseek": [{"id": "deepseek-chat", "name": "DeepSeek Chat"}],
                    "gemini": [{"id": "gemini-pro", "name": "Gemini Pro"}]
                }
        except Exception as e:
            st.warning(f"Errore nel recupero dei modelli: {e}")
            return {
                "openai": [{"id": "gpt-4o-mini", "name": "GPT-4o Mini"}],
                "claude": [{"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku"}],
                "deepseek": [{"id": "deepseek-chat", "name": "DeepSeek Chat"}],
                "gemini": [{"id": "gemini-pro", "name": "Gemini Pro"}]
            }

    def get_models_for_provider(self, provider):
        """
        Restituisce i modelli disponibili per un provider specifico.

        Args:
            provider (str): Il nome del provider (es. 'openai', 'claude')

        Returns:
            list: Lista dei modelli disponibili per il provider
        """
        if provider in self.available_models:
            return self.available_models[provider]
        return []
