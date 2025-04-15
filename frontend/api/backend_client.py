"""
Gestisce le chiamate API al backend.
"""
import requests  # type: ignore


class BackendClient:
    """Gestisce le chiamate API al backend."""

    def __init__(self, backend_url):
        """Inizializza il client backend."""
        self.backend_url = backend_url

    def execute_query(self, domanda, llm_config, ssh_config, db_config, force_no_cache=False):
        """
        Invia la richiesta di query e restituisce l'ID.

        Args:
            domanda (str): La domanda da analizzare
            llm_config (dict): Configurazione del modello LLM
            ssh_config (dict): Configurazione SSH
            db_config (dict): Configurazione del database
            force_no_cache (bool): Se True, forza la rigenerazione ignorando la cache

        Returns:
            Response: Oggetto risposta HTTP
        """
        response = requests.post(
            f"{self.backend_url}/query",
            json={
                "domanda": domanda,
                "llm_config": llm_config,
                "ssh_config": ssh_config,
                "db_config": db_config,
                "force_no_cache": force_no_cache
            }
        )
        return response

    def get_query_status(self, query_id):
        """
        Recupera lo stato di una query.

        Args:
            query_id (str): ID della query

        Returns:
            Response: Oggetto risposta HTTP
        """
        response = requests.get(f"{self.backend_url}/query_status/{query_id}")
        return response

    def refresh_schema(self, ssh_config, db_config):
        """
        Aggiorna lo schema del database.

        Args:
            ssh_config (dict): Configurazione SSH
            db_config (dict): Configurazione del database

        Returns:
            Response: Oggetto risposta HTTP
        """
        response = requests.post(
            f"{self.backend_url}/refresh_schema",
            json={
                "ssh_config": ssh_config,
                "db_config": db_config
            }
        )
        return response

    def test_connection(self, ssh_config, db_config):
        """
        Testa la connessione SSH e al database.

        Args:
            ssh_config (dict): Configurazione SSH
            db_config (dict): Configurazione del database

        Returns:
            Response: Oggetto risposta HTTP
        """
        response = requests.post(
            f"{self.backend_url}/test_connection",
            json={
                "ssh_config": ssh_config,
                "db_config": db_config
            }
        )
        return response

    def get_related_questions(self, query_id, max_questions=5):
        """
        Ottiene domande correlate per una query completata.

        Args:
            query_id (str): ID della query completata
            max_questions (int): Numero massimo di domande da generare

        Returns:
            Response: Oggetto risposta HTTP
        """
        response = requests.post(
            f"{self.backend_url}/related_questions/{query_id}",
            params={"max_questions": max_questions}
        )
        return response
