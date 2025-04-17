"""
Sistema di gestione delle valutazioni degli utenti sulle analisi.
Consente di salvare e recuperare il feedback degli utenti sulle query eseguite.
"""
import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, create_engine, desc  # type: ignore
from sqlalchemy.orm import sessionmaker, declarative_base  # type: ignore
from backend.utils.logging import get_logger
from backend.config import RATING_DB_URL

logger = get_logger(__name__)

# Definizione del modello del database
Base = declarative_base()


class QueryRating(Base):
    """Modello per la tabella delle valutazioni delle query."""
    __tablename__ = "query_ratings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_id = Column(String, nullable=False, index=True)
    domanda = Column(Text, nullable=False)
    query_sql = Column(Text, nullable=False)
    positive = Column(Boolean, nullable=False)
    feedback = Column(Text, nullable=True)
    timestamp = Column(String, default=lambda: datetime.now().isoformat())
    llm_provider = Column(String, nullable=True)

    def __repr__(self):
        return f"<QueryRating(id='{self.id}', query_id='{self.query_id}', positive='{self.positive}')>"


class AnalysisResult(Base):
    """Modello per la tabella dei risultati delle analisi."""
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_id = Column(String, nullable=False, index=True)
    domanda = Column(Text, nullable=False)
    query_sql = Column(Text, nullable=False)
    descrizione = Column(Text, nullable=True)
    dati_json = Column(Text, nullable=True)  # JSON serializzato dei risultati
    grafico_path = Column(String, nullable=True)
    timestamp = Column(String, default=lambda: datetime.now().isoformat())
    llm_provider = Column(String, nullable=True)
    cache_used = Column(Boolean, default=False)
    execution_time = Column(Integer, nullable=True)  # Tempo in millisecondi
    error = Column(Text, nullable=True)  # Messaggio di errore
    error_traceback = Column(Text, nullable=True)  # Traceback completo dell'errore

    def __repr__(self):
        return f"<AnalysisResult(id='{self.id}', query_id='{self.query_id}')>"


class RatingStore:
    """Gestisce il database delle valutazioni."""

    def __init__(self, db_url=RATING_DB_URL):
        """
        Inizializza il database delle valutazioni.

        Args:
            db_url (str): URL di connessione al database
        """
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def save_rating(self, query_id, domanda, query_sql, positive, feedback, llm_provider=None):
        """
        Salva una valutazione di query nel database.

        Args:
            query_id (str): ID della query
            domanda (str): La domanda dell'utente
            query_sql (str): La query SQL eseguita
            positive (bool): Se la valutazione è positiva
            feedback (str): Feedback testuale dell'utente
            llm_provider (str, optional): Provider LLM utilizzato

        Returns:
            int: L'ID della valutazione inserita
        """
        try:
            session = self.Session()

            # Verifica se esiste già una valutazione per questa query
            existing = session.query(QueryRating).filter_by(query_id=query_id).first()

            if existing:
                # Aggiorna la valutazione esistente
                existing.positive = positive
                existing.feedback = feedback
                existing.timestamp = datetime.now().isoformat()
                session.commit()
                rating_id = existing.id
                logger.info(f"✅ Aggiornata valutazione per query ID: {query_id}")
            else:
                # Crea una nuova valutazione
                rating = QueryRating(
                    query_id=query_id,
                    domanda=domanda,
                    query_sql=query_sql,
                    positive=positive,
                    feedback=feedback,
                    llm_provider=llm_provider
                )
                session.add(rating)
                session.commit()
                rating_id = rating.id
                logger.info(f"✅ Aggiunta nuova valutazione per query ID: {query_id}")

            session.close()
            return rating_id
        except Exception as e:
            logger.error(f"❌ Errore nel salvataggio della valutazione: {e}")
            return None

    def save_analysis_result(
            self, query_id, domanda, query_sql=None, descrizione=None, dati=None, grafico_path=None,
            llm_provider=None, cache_used=False, execution_time=None, error=None, error_traceback=None):
        """
        Salva il risultato di un'analisi nel database.

        Args:
            query_id (str): ID della query
            domanda (str): La domanda dell'utente
            query_sql (str, optional): La query SQL eseguita
            descrizione (str, optional): Descrizione testuale dei risultati
            dati (list, optional): Dati risultanti dall'analisi
            grafico_path (str, optional): Percorso del grafico generato
            llm_provider (str, optional): Provider LLM utilizzato
            cache_used (bool): Se è stata usata la cache
            execution_time (int, optional): Tempo di esecuzione in ms
            error (str, optional): Messaggio di errore se presente
            error_traceback (str, optional): Traceback completo dell'errore se presente

        Returns:
            int: L'ID del risultato inserito
        """
        try:
            session = self.Session()

            # Converti i dati in JSON
            dati_json = json.dumps(dati) if dati else None

            # Verifica se esiste già un risultato per questa query
            existing = session.query(AnalysisResult).filter_by(query_id=query_id).first()

            if existing:
                # Aggiorna il risultato esistente
                existing.domanda = domanda
                if query_sql is not None:
                    existing.query_sql = query_sql
                if descrizione is not None:
                    existing.descrizione = descrizione
                if dati_json is not None:
                    existing.dati_json = dati_json
                if grafico_path is not None:
                    existing.grafico_path = grafico_path
                if llm_provider is not None:
                    existing.llm_provider = llm_provider
                existing.cache_used = cache_used
                if execution_time is not None:
                    existing.execution_time = execution_time
                if error is not None:
                    existing.error = error
                if error_traceback is not None:
                    existing.error_traceback = error_traceback
                existing.timestamp = datetime.now().isoformat()
                session.commit()
                result_id = existing.id
                logger.info(f"✅ Aggiornato risultato per query ID: {query_id}")
            else:
                # Crea un nuovo risultato
                result = AnalysisResult(
                    query_id=query_id,
                    domanda=domanda,
                    query_sql=query_sql,
                    descrizione=descrizione,
                    dati_json=dati_json,
                    grafico_path=grafico_path,
                    llm_provider=llm_provider,
                    cache_used=cache_used,
                    execution_time=execution_time,
                    error=error,
                    error_traceback=error_traceback
                )
                session.add(result)
                session.commit()
                result_id = result.id
                logger.info(f"✅ Aggiunto nuovo risultato per query ID: {query_id}")

            session.close()
            return result_id
        except Exception as e:
            logger.error(f"❌ Errore nel salvataggio del risultato: {e}")
            return None

    def get_rating(self, query_id):
        """
        Recupera una valutazione specifica.

        Args:
            query_id (str): ID della query da recuperare

        Returns:
            dict: Dati della valutazione o None se non trovata
        """
        try:
            session = self.Session()
            rating = session.query(QueryRating).filter_by(query_id=query_id).first()
            session.close()

            if rating:
                return {
                    "id": rating.id,
                    "query_id": rating.query_id,
                    "domanda": rating.domanda,
                    "query_sql": rating.query_sql,
                    "positive": rating.positive,
                    "feedback": rating.feedback,
                    "timestamp": rating.timestamp,
                    "llm_provider": rating.llm_provider
                }
            else:
                return None
        except Exception as e:
            logger.error(f"❌ Errore nel recupero della valutazione: {e}")
            return None

    def get_analysis_result(self, query_id):
        """
        Recupera un risultato di analisi specifico.

        Args:
            query_id (str): ID della query da recuperare

        Returns:
            dict: Dati del risultato o None se non trovato
        """
        try:
            session = self.Session()
            result = session.query(AnalysisResult).filter_by(query_id=query_id).first()
            session.close()

            if result:
                # Converti il JSON in lista
                dati = json.loads(result.dati_json) if result.dati_json else []

                return {
                    "id": result.id,
                    "query_id": result.query_id,
                    "domanda": result.domanda,
                    "query_sql": result.query_sql,
                    "descrizione": result.descrizione,
                    "dati": dati,
                    "grafico_path": result.grafico_path,
                    "timestamp": result.timestamp,
                    "llm_provider": result.llm_provider,
                    "cache_used": result.cache_used,
                    "execution_time": result.execution_time,
                    "error": result.error,
                    "error_traceback": result.error_traceback,
                    "has_error": result.error is not None and len(result.error) > 0
                }
            else:
                return None
        except Exception as e:
            logger.error(f"❌ Errore nel recupero del risultato: {e}")
            return None

    def get_all_analysis_results(self, limit=50, offset=0):
        """
        Recupera tutti i risultati delle analisi, ordinati per data (più recenti prima).

        Args:
            limit (int): Limite di risultati
            offset (int): Offset per la paginazione

        Returns:
            list: Lista di risultati
        """
        try:
            session = self.Session()
            results = session.query(AnalysisResult).order_by(
                desc(AnalysisResult.timestamp)
            ).offset(offset).limit(limit).all()
            session.close()

            return [
                {
                    "id": result.id,
                    "query_id": result.query_id,
                    "domanda": result.domanda,
                    "timestamp": result.timestamp,
                    "llm_provider": result.llm_provider,
                    "cache_used": result.cache_used
                }
                for result in results
            ]
        except Exception as e:
            logger.error(f"❌ Errore nel recupero dei risultati: {e}")
            return []

    def get_ratings_stats(self):
        """
        Ottiene statistiche sulle valutazioni.

        Returns:
            dict: Statistiche sulle valutazioni
        """
        try:
            session = self.Session()
            total = session.query(QueryRating).count()
            positive = session.query(QueryRating).filter_by(positive=True).count()
            negative = session.query(QueryRating).filter_by(positive=False).count()
            session.close()

            return {
                "total": total,
                "positive": positive,
                "negative": negative,
                "positive_percentage": (positive / total * 100) if total > 0 else 0
            }
        except Exception as e:
            logger.error(f"❌ Errore nel recupero delle statistiche: {e}")
            return {"total": 0, "positive": 0, "negative": 0, "positive_percentage": 0}
