"""
Sistema di caching intelligente per le query SQL.
Gestisce il salvataggio, il recupero e l'aggiornamento delle query in cache.
"""
import numpy as np  # type: ignore
import os
import faiss  # type: ignore
from sqlalchemy import Column, String, Text, create_engine  # type: ignore
from sqlalchemy.orm import sessionmaker, declarative_base  # type: ignore
from sqlalchemy.exc import IntegrityError  # type: ignore
from sentence_transformers import SentenceTransformer  # type: ignore
from backend.utils.logging import get_logger
from backend.config import DB_URL, EMBEDDINGS_PATH, MAX_ACCEPTABLE_DISTANCE

# Configura il logging
logger = get_logger(__name__)

# Definizione del modello del database
Base = declarative_base()


class QueryCache(Base):
    """Modello per la tabella della cache delle query."""
    __tablename__ = "query_cache"

    domanda = Column(String, primary_key=True)
    embedding = Column(String)  # Serializzazione dell'embedding
    query_sql = Column(Text)
    db_hash = Column(String)

    def __repr__(self):
        return f"<QueryCache(domanda='{self.domanda}', query_sql='{self.query_sql[:30]}...')>"


class QueryCacheManager:
    """Gestisce la cache delle query SQL."""

    def __init__(self, db_url=DB_URL, embeddings_path=EMBEDDINGS_PATH):
        """
        Inizializza il gestore della cache.

        Args:
            db_url (str): URL di connessione al database
            embeddings_path (str): Directory per il salvataggio/caricamento degli embeddings
        """
        self.db_url = db_url
        self.embeddings_path = embeddings_path

        # Inizializzazione del database
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        # Caricamento del modello per gli embeddings
        self.model = None
        self.index = None
        self.id_to_domanda = {}

        # Carica il modello e l'indice FAISS
        self.load_embedding_model()

    def load_embedding_model(self):
        """Carica il modello di embedding e l'indice FAISS."""
        try:
            if self.model is None:
                logger.info("Caricamento del modello di embedding...")
                # Modello multilingue compatto che supporta italiano
                self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                logger.info(f"Modello caricato: dimensione vettori = {self.model.get_sentence_embedding_dimension()}")

            # Assicuriamo che la directory esista
            os.makedirs(self.embeddings_path, exist_ok=True)

            # Caricamento dell'indice FAISS se esiste
            faiss_index_path = os.path.join(self.embeddings_path, "faiss_index.bin")
            mapping_path = os.path.join(self.embeddings_path, "id_to_domanda.npy")

            if os.path.exists(faiss_index_path) and os.path.exists(mapping_path):
                logger.info(f"Caricamento dell'indice FAISS esistente da {faiss_index_path}...")
                self.index = faiss.read_index(faiss_index_path)
                self.id_to_domanda = np.load(mapping_path, allow_pickle=True).item()
                logger.info(f"Indice FAISS caricato con {self.index.ntotal} vettori")
            else:
                logger.info("Creazione di un nuovo indice FAISS...")
                self._rebuild_faiss_index()
        except Exception as e:
            logger.error(f"Errore nel caricamento del modello di embedding: {e}")
            raise

    def _rebuild_faiss_index(self):
        """Ricostruisce l'indice FAISS dalle query in cache."""
        try:
            logger.info("Ricostruzione dell'indice FAISS...")

            # Carica il modello di embedding se non è già caricato
            if self.model is None:
                self.load_embedding_model()

            # Recupera tutte le domande dal database
            session = self.Session()
            query_cache_entries = session.query(QueryCache).all()
            session.close()

            # Assicuriamo che le directory esistano
            os.makedirs(self.embeddings_path, exist_ok=True)

            # Percorsi dei file
            faiss_index_path = os.path.join(self.embeddings_path, "faiss_index.bin")
            mapping_path = os.path.join(self.embeddings_path, "id_to_domanda.npy")

            if query_cache_entries:
                # Ottieni gli embeddings e crea l'indice
                domande = [entry.domanda for entry in query_cache_entries]
                logger.info(f"Generazione embeddings per {len(domande)} domande...")
                embeddings = self.model.encode(domande)

                # Crea l'indice FAISS
                vector_dimension = embeddings.shape[1]
                self.index = faiss.IndexFlatL2(vector_dimension)
                self.index.add(np.array(embeddings).astype('float32'))

                # Crea la mappatura degli indici
                self.id_to_domanda = {i: domanda for i, domanda in enumerate(domande)}

                # Salva l'indice e la mappatura
                faiss.write_index(self.index, faiss_index_path)
                np.save(mapping_path, self.id_to_domanda)

                logger.info(f"Indice FAISS ricostruito con {len(domande)} query in cache e salvato in {faiss_index_path}")
            else:
                # Crea un indice vuoto
                if self.model:
                    vector_dimension = self.model.get_sentence_embedding_dimension()
                    self.index = faiss.IndexFlatL2(vector_dimension)
                    self.id_to_domanda = {}

                    # Salva l'indice vuoto
                    faiss.write_index(self.index, faiss_index_path)
                    np.save(mapping_path, self.id_to_domanda)

                    logger.info("Indice FAISS vuoto creato (nessuna query in cache)")
                else:
                    logger.warning("Impossibile creare indice FAISS: modello non caricato")
        except Exception as e:
            logger.error(f"Errore nella ricostruzione dell'indice FAISS: {e}")

    def get_cached_query(self, domanda, similarity_threshold=0.85, db_hash=None):
        """
        Cerca una query simile nella cache usando embeddings.

        Args:
            domanda (str): La domanda dell'utente
            similarity_threshold (float): Soglia di similarità (0-1) - parametro mantenuto per compatibilità
            db_hash (str, optional): Hash della struttura del database attuale

        Returns:
            str: La query SQL dalla cache se esiste una voce simile, altrimenti None
        """
        try:
            # Prima verifichiamo se la domanda esatta esiste nella cache
            # Questo è più veloce che usare FAISS per domande identiche
            session = self.Session()
            exact_match = session.query(QueryCache).filter_by(domanda=domanda).first()
            session.close()

            if exact_match:
                # Verifica se la struttura del database è cambiata
                if (exact_match.db_hash == db_hash or not exact_match.db_hash or not db_hash):
                    logger.info(f"✅ Trovata corrispondenza esatta per la domanda '{domanda}'")
                    return exact_match.query_sql
                else:
                    logger.info("⚠️ Schema DB cambiato, ignoro la corrispondenza esatta")

            # Carica il modello di embedding se non è già caricato
            if self.model is None or self.index is None:
                self.load_embedding_model()

            # Calcola l'embedding della domanda
            embedding = self.model.encode([domanda])

            # Cerca le domande più simili nell'indice
            if self.index and self.index.ntotal > 0:
                distances, indices = self.index.search(embedding.astype('float32'), 1)

                # Log per debug
                logger.info(f"Query: '{domanda}' - Distanza minima trovata: {distances[0][0]}")

                # FAISS usa distanze L2: valori più bassi indicano maggiore similarità
                if distances[0][0] < MAX_ACCEPTABLE_DISTANCE:
                    similar_question_idx = indices[0][0]
                    similar_question = self.id_to_domanda[similar_question_idx]

                    logger.info(f"Query simile trovata: '{similar_question}' con distanza {distances[0][0]}")

                    # Recupera la query SQL dal database
                    session = self.Session()
                    cache_entry = session.query(QueryCache).filter_by(domanda=similar_question).first()
                    session.close()

                    if cache_entry:
                        # Verifica se la struttura del database è cambiata
                        if (cache_entry.db_hash == db_hash or not cache_entry.db_hash or not db_hash):
                            logger.info(f"✅ Utilizzando query in cache per '{similar_question}'")
                            return cache_entry.query_sql
                        else:
                            logger.info(f"⚠️ Schema DB cambiato, ignoro la query in cache per '{similar_question}'")
                    else:
                        logger.info("⚠️ Incoerenza nell'indice FAISS: domanda trovata nell'indice ma non nel DB")
                else:
                    logger.info(
                        f"⚠️ Nessuna query simile trovata (distanza minima {distances[0][0]} > soglia {MAX_ACCEPTABLE_DISTANCE})"
                    )
            else:
                logger.info("⚠️ Indice FAISS vuoto o non inizializzato")

            return None
        except Exception as e:
            logger.error(f"Errore nel recupero della query dalla cache: {e}")
            return None

    def save_query_to_cache(self, domanda, query_sql, db_hash=None):
        """
        Salva una nuova query nella cache o aggiorna una esistente.

        Args:
            domanda (str): La domanda dell'utente
            query_sql (str): La query SQL generata
            db_hash (str, optional): L'hash della struttura del database corrente

        Returns:
            bool: True se l'operazione è riuscita, False altrimenti
        """
        try:
            # Sanitizza la domanda e la query
            domanda = domanda.strip()
            query_sql = query_sql.strip()

            if not domanda or not query_sql:
                logger.warning("Tentativo di salvare una domanda o query vuota.")
                return False

            # Carica il modello di embedding se non è già caricato
            if self.model is None:
                self.load_embedding_model()

            # Calcola l'embedding della domanda
            embedding = self.model.encode([domanda])[0]

            # Salva o aggiorna la query nel database
            session = self.Session()

            try:
                # Prima verifichiamo se esiste già questa domanda
                existing_entry = session.query(QueryCache).filter_by(domanda=domanda).first()

                if existing_entry:
                    # Aggiorniamo l'entry esistente
                    existing_entry.query_sql = query_sql
                    if db_hash:
                        existing_entry.db_hash = db_hash
                    session.commit()
                    logger.info(f"Query aggiornata per '{domanda}'")
                else:
                    # Creiamo una nuova entry
                    cache_entry = QueryCache(
                        domanda=domanda,
                        embedding=','.join(map(str, embedding)),
                        query_sql=query_sql,
                        db_hash=db_hash if db_hash else None
                    )
                    session.add(cache_entry)
                    session.commit()
                    logger.info(f"Nuova query salvata per '{domanda}'")

                # Aggiorna l'indice FAISS
                self._rebuild_faiss_index()

                return True
            except IntegrityError:
                session.rollback()
                # Se abbiamo un errore di integrità, proviamo ad aggiornare
                try:
                    existing_entry = session.query(QueryCache).filter_by(domanda=domanda).first()
                    if existing_entry:
                        existing_entry.query_sql = query_sql
                        if db_hash:
                            existing_entry.db_hash = db_hash
                        session.commit()
                        logger.info(f"Query aggiornata per '{domanda}' dopo errore di integrità")
                        self._rebuild_faiss_index()
                        return True
                except Exception as e:
                    session.rollback()
                    logger.error(f"Errore nell'aggiornamento dopo errore di integrità: {e}")
                    return False
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Errore nel salvataggio della query nella cache: {e}")
            return False

    def delete_cached_query(self, domanda):
        """
        Elimina una query dalla cache.

        Args:
            domanda (str): La domanda da eliminare

        Returns:
            bool: True se l'operazione è riuscita, False altrimenti
        """
        try:
            session = self.Session()
            cache_entry = session.query(QueryCache).filter_by(domanda=domanda).first()

            if cache_entry:
                session.delete(cache_entry)
                session.commit()
                session.close()

                # Aggiorna l'indice FAISS
                self._rebuild_faiss_index()

                logger.info(f"Query eliminata per '{domanda}'")
                return True
            else:
                session.close()
                logger.warning(f"Nessuna query trovata per '{domanda}'")
                return False
        except Exception as e:
            logger.error(f"Errore nell'eliminazione della query dalla cache: {e}")
            return False
