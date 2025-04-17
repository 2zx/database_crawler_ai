"""
Gestisce le operazioni relative alle valutazioni delle query e allo storico.
"""
import requests  # type: ignore
import streamlit as st  # type: ignore


class RatingManager:
    """Gestisce le operazioni relative alle valutazioni delle query e allo storico."""

    def __init__(self, backend_url):
        """
        Inizializza il gestore delle valutazioni.

        Args:
            backend_url (str): URL dell'API backend
        """
        self.backend_url = backend_url

    def submit_rating(self, query_id, domanda, query_sql, positive, feedback="", llm_provider=None):
        """
        Invia una valutazione per una query.

        Args:
            query_id (str): ID della query
            domanda (str): Domanda originale
            query_sql (str): Query SQL eseguita
            positive (bool): Se la valutazione è positiva
            feedback (str, optional): Feedback testuale dell'utente
            llm_provider (str, optional): Provider LLM utilizzato

        Returns:
            bool: True se l'invio è riuscito, False altrimenti
        """
        try:
            response = requests.post(
                f"{self.backend_url}/ratings",
                json={
                    "query_id": query_id,
                    "domanda": domanda,
                    "query_sql": query_sql,
                    "positive": positive,
                    "feedback": feedback,
                    "llm_provider": llm_provider
                }
            )
            if response.status_code == 200:
                return True
            else:
                st.warning(f"Errore nell'invio della valutazione: {response.text}")
                return False
        except Exception as e:
            st.warning(f"Errore nell'invio della valutazione: {e}")
            return False

    def save_analysis_result(
            self, query_id, domanda, query_sql, descrizione, dati, grafico_path,
            llm_provider=None, cache_used=False, execution_time=None):
        """
        Salva il risultato di un'analisi.

        Args:
            query_id (str): ID della query
            domanda (str): Domanda originale
            query_sql (str): Query SQL eseguita
            descrizione (str): Descrizione testuale dei risultati
            dati (list): Dati risultanti dall'analisi
            grafico_path (str): Percorso del grafico generato
            llm_provider (str, optional): Provider LLM utilizzato
            cache_used (bool): Se è stata usata la cache
            execution_time (int, optional): Tempo di esecuzione in ms

        Returns:
            bool: True se il salvataggio è riuscito, False altrimenti
        """
        try:
            response = requests.post(
                f"{self.backend_url}/analysis_results",
                json={
                    "query_id": query_id,
                    "domanda": domanda,
                    "query_sql": query_sql,
                    "descrizione": descrizione,
                    "dati": dati,
                    "grafico_path": grafico_path,
                    "llm_provider": llm_provider,
                    "cache_used": cache_used,
                    "execution_time": execution_time
                }
            )
            if response.status_code == 200:
                return True
            else:
                st.warning(f"Errore nel salvataggio del risultato: {response.text}")
                return False
        except Exception as e:
            st.warning(f"Errore nel salvataggio del risultato: {e}")
            return False

    def get_rating(self, query_id):
        """
        Recupera una valutazione specifica.

        Args:
            query_id (str): ID della query

        Returns:
            dict or None: Dati della valutazione o None se non trovata
        """
        try:
            response = requests.get(f"{self.backend_url}/ratings/{query_id}")
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception as e:
            st.warning(f"Errore nel recupero della valutazione: {e}")
            return None

    def get_analysis_result(self, query_id):
        """
        Recupera un risultato di analisi specifico.

        Args:
            query_id (str): ID della query

        Returns:
            dict or None: Dati del risultato o None se non trovato
        """
        try:
            response = requests.get(f"{self.backend_url}/analysis_results/{query_id}")
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception as e:
            st.warning(f"Errore nel recupero del risultato: {e}")
            return None

    def get_all_analysis_results(self, limit=50, offset=0):
        """
        Recupera tutti i risultati delle analisi.

        Args:
            limit (int): Limite di risultati
            offset (int): Offset per la paginazione

        Returns:
            list: Lista di risultati
        """
        try:
            response = requests.get(
                f"{self.backend_url}/analysis_results",
                params={"limit": limit, "offset": offset}
            )
            if response.status_code == 200:
                return response.json()
            else:
                st.warning("Non è stato possibile recuperare i risultati.")
                return []
        except Exception as e:
            st.warning(f"Errore nel recupero dei risultati: {e}")
            return []

    def get_ratings_stats(self):
        """
        Ottiene statistiche sulle valutazioni.

        Returns:
            dict: Statistiche sulle valutazioni
        """
        try:
            response = requests.get(f"{self.backend_url}/ratings/stats")
            if response.status_code == 200:
                return response.json()
            else:
                st.warning("Non è stato possibile recuperare le statistiche.")
                return {"total": 0, "positive": 0, "negative": 0, "positive_percentage": 0}
        except Exception as e:
            st.warning(f"Errore nel recupero delle statistiche: {e}")
            return {"total": 0, "positive": 0, "negative": 0, "positive_percentage": 0}
