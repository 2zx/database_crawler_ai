"""
Gestisce il caricamento e il salvataggio delle credenziali.
"""
import os
import json
from frontend.config import LLM_PROVIDERS


class CredentialsManager:
    """Gestisce il caricamento e il salvataggio delle credenziali."""

    def __init__(self, credentials_file):
        """Inizializza il gestore delle credenziali."""
        self.credentials_file = credentials_file
        self.credentials = self.load_credentials()

    def load_credentials(self):
        """Carica le credenziali salvate dal file."""
        if os.path.exists(self.credentials_file):
            with open(self.credentials_file, "r") as file:
                return json.load(file)
        return {}

    def save_credentials(self):
        """Salva le credenziali nel file."""
        # Assicuriamoci che la directory esista
        os.makedirs(os.path.dirname(self.credentials_file), exist_ok=True)

        with open(self.credentials_file, "w") as file:
            json.dump(self.credentials, file)

    def get_ssh_config(self):
        """Restituisce la configurazione SSH."""
        return {
            "ssh_host": self.credentials.get("ssh_host", ""),
            "ssh_user": self.credentials.get("ssh_user", ""),
            "ssh_key": self.credentials.get("ssh_key", ""),
            "use_ssh": self.credentials.get("use_ssh", False)
        }

    def get_db_config(self):
        """Restituisce la configurazione del database."""
        return {
            "host": self.credentials.get("db_host", ""),
            "port": self.credentials.get("db_port", ""),
            "user": self.credentials.get("db_user", ""),
            "password": self.credentials.get("db_password", ""),
            "database": self.credentials.get("db_name", ""),
            "db_type": self.credentials.get("db_type", "postgresql"),
            "hint_category": self.credentials.get("hint_category", "generale")
        }

    def get_llm_config(self):
        """Restituisce la configurazione del LLM selezionato."""
        provider = self.credentials.get("llm_provider", "openai")
        config = {
            "provider": provider,
            "api_key": self.credentials.get(LLM_PROVIDERS[provider]["api_key_name"], ""),
            "model": self.credentials.get(f"{provider}_model", "")
        }

        # Aggiungi secret_key per Baidu ERNIE se necessario
        if provider == "ernie" and LLM_PROVIDERS[provider]["requires_secret"]:
            config["secret_key"] = self.credentials.get(LLM_PROVIDERS[provider]["secret_key_name"], "")

        return config
