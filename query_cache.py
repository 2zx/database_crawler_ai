"""
Sistema di caching intelligente per le query SQL.
Gestisce il salvataggio, il recupero e l'aggiornamento delle query in cache.
"""
import logging
from sqlalchemy import Column, String, Text, create_engine  # type: ignore
from sqlalchemy.orm import sessionmaker, declarative_base  # type: ignore
from sqlalchemy.exc import IntegrityError  # type: ignore
import numpy as np  # type: ignore
from sentence_transformers import SentenceTransformer  # type: ignore
import faiss  # type: ignore
import os
from config import DB_URL, EMBEDDINGS_PATH

# Configura il logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


# Inizializzazione del database
engine = create_engine(DB_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# Caricamento del modello per gli embeddings
model = None
index = None
id_to_domanda = {}

# Costanti per la ricerca di similarità
MAX_ACCEPTABLE_DISTANCE = 0.5  # Soglia di distanza massima per considerare due domande simili


def load_embedding_model():
    """Carica il modello di embedding e l'indice FAISS."""
    global model, index, id_to_domanda
    try:
        if model is None:
            logger.info("Caricamento del modello di embedding...")
            # Modello multilingue compatto che supporta italiano
            model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            logger.info(f"Modello caricato: dimensione vettori = {model.get_sentence_embedding_dimension()}")

        # Assicuriamo che la directory esista
        os.makedirs(EMBEDDINGS_PATH, exist_ok=True)

        # Caricamento dell'indice FAISS se esiste
        faiss_index_path = os.path.join(EMBEDDINGS_PATH, "faiss_index.bin")
        mapping_path = os.path.join(EMBEDDINGS_PATH, "id_to_domanda.npy")

        if os.path.exists(faiss_index_path) and os.path.exists(mapping_path):
            logger.info(f"Caricamento dell'indice FAISS esistente da {faiss_index_path}...")
            index = faiss.read_index(faiss_index_path)
            id_to_domanda = np.load(mapping_path, allow_pickle=True).item()
            logger.info(f"Indice FAISS caricato con {index.ntotal} vettori")
        else:
            logger.info("Creazione di un nuovo indice FAISS...")
            # Recupera tutte le domande dal database
            session = Session()
            query_cache_entries = session.query(QueryCache).all()
            session.close()

            logger.info(f"Trovate {len(query_cache_entries)} query in cache")

            if query_cache_entries:
                # Ottieni gli embeddings e crea l'indice
                domande = [entry.domanda for entry in query_cache_entries]
                embeddings = model.encode(domande)
                logger.info(f"Generati {len(embeddings)} vettori di embedding")

                # Crea l'indice FAISS
                vector_dimension = embeddings.shape[1]
                index = faiss.IndexFlatL2(vector_dimension)
                index.add(np.array(embeddings).astype('float32'))
                logger.info(f"Indice FAISS creato con dimensione {vector_dimension}")

                # Crea la mappatura degli indici
                id_to_domanda = {i: domanda for i, domanda in enumerate(domande)}

                # Salva l'indice e la mappatura
                faiss.write_index(index, faiss_index_path)
                np.save(mapping_path, id_to_domanda)
                logger.info(f"Indice FAISS salvato in {faiss_index_path}")
            else:
                # Crea un indice vuoto con la dimensione corretta
                vector_dimension = model.get_sentence_embedding_dimension()
                index = faiss.IndexFlatL2(vector_dimension)
                id_to_domanda = {}
                logger.info(f"Creato indice FAISS vuoto con dimensione {vector_dimension}")
    except Exception as e:
        logger.error(f"Errore nel caricamento del modello di embedding: {e}")
        raise


def rebuild_faiss_index():
    """Ricostruisce l'indice FAISS dalle query in cache."""
    global index, id_to_domanda
    try:
        logger.info("Ricostruzione dell'indice FAISS...")

        # Carica il modello di embedding se non è già caricato
        if model is None:
            load_embedding_model()

        # Recupera tutte le domande dal database
        session = Session()
        query_cache_entries = session.query(QueryCache).all()
        session.close()

        # Assicuriamo che le directory esistano
        os.makedirs(EMBEDDINGS_PATH, exist_ok=True)

        # Percorsi dei file
        faiss_index_path = os.path.join(EMBEDDINGS_PATH, "faiss_index.bin")
        mapping_path = os.path.join(EMBEDDINGS_PATH, "id_to_domanda.npy")

        if query_cache_entries:
            # Ottieni gli embeddings e crea l'indice
            domande = [entry.domanda for entry in query_cache_entries]
            logger.info(f"Generazione embeddings per {len(domande)} domande...")
            embeddings = model.encode(domande)

            # Crea l'indice FAISS
            vector_dimension = embeddings.shape[1]
            index = faiss.IndexFlatL2(vector_dimension)
            index.add(np.array(embeddings).astype('float32'))

            # Crea la mappatura degli indici
            id_to_domanda = {i: domanda for i, domanda in enumerate(domande)}

            # Salva l'indice e la mappatura
            faiss.write_index(index, faiss_index_path)
            np.save(mapping_path, id_to_domanda)

            logger.info(f"Indice FAISS ricostruito con {len(domande)} query in cache e salvato in {faiss_index_path}")
        else:
            # Crea un indice vuoto
            if model:
                vector_dimension = model.get_sentence_embedding_dimension()
                index = faiss.IndexFlatL2(vector_dimension)
                id_to_domanda = {}

                # Salva l'indice vuoto
                faiss.write_index(index, faiss_index_path)
                np.save(mapping_path, id_to_domanda)

                logger.info("Indice FAISS vuoto creato (nessuna query in cache)")
            else:
                logger.warning("Impossibile creare indice FAISS: modello non caricato")
    except Exception as e:
        logger.error(f"Errore nella ricostruzione dell'indice FAISS: {e}")


def get_cached_query(domanda, similarity_threshold=0.85):
    """
    Cerca una query simile nella cache usando embeddings.

    Args:
        domanda: La domanda dell'utente
        similarity_threshold: Soglia di similarità (0-1) - parametro mantenuto per compatibilità

    Returns:
        La query SQL dalla cache se esiste una voce simile, altrimenti None
    """
    try:
        # Prima verifichiamo se la domanda esatta esiste nella cache
        # Questo è più veloce che usare FAISS per domande identiche
        session = Session()
        exact_match = session.query(QueryCache).filter_by(domanda=domanda).first()
        session.close()

        if exact_match:
            # Ottieni l'hash della struttura del database corrente
            from db_schema import get_db_structure_hash
            current_db_hash = get_db_structure_hash() or ""

            # Verifica se la struttura del database è cambiata
            if exact_match.db_hash == current_db_hash or not exact_match.db_hash:
                logger.info(f"✅ Trovata corrispondenza esatta per la domanda '{domanda}'")
                return exact_match.query_sql
            else:
                logger.info("⚠️ Schema DB cambiato, ignoro la corrispondenza esatta")

        # Ottieni l'hash della struttura del database corrente
        from db_schema import get_db_structure_hash
        current_db_hash = get_db_structure_hash() or ""

        # Carica il modello di embedding se non è già caricato
        if model is None or index is None:
            load_embedding_model()

        # Calcola l'embedding della domanda
        embedding = model.encode([domanda])

        # Cerca le domande più simili nell'indice
        if index and index.ntotal > 0:
            distances, indices = index.search(embedding.astype('float32'), 1)

            # Log per debug
            logger.info(f"Query: '{domanda}' - Distanza minima trovata: {distances[0][0]}")

            # FAISS usa distanze L2: valori più bassi indicano maggiore similarità
            if distances[0][0] < MAX_ACCEPTABLE_DISTANCE:
                similar_question_idx = indices[0][0]
                similar_question = id_to_domanda[similar_question_idx]

                logger.info(f"Query simile trovata: '{similar_question}' con distanza {distances[0][0]}")

                # Recupera la query SQL dal database
                session = Session()
                cache_entry = session.query(QueryCache).filter_by(domanda=similar_question).first()
                session.close()

                if cache_entry:
                    # Verifica se la struttura del database è cambiata
                    if cache_entry.db_hash == current_db_hash or not cache_entry.db_hash:
                        logger.info(f"✅ Utilizzando query in cache per '{similar_question}'")
                        return cache_entry.query_sql
                    else:
                        logger.info(f"⚠️ Schema DB cambiato, ignoro la query in cache per '{similar_question}'")
                else:
                    logger.info("⚠️ Incoerenza nell'indice FAISS: domanda trovata nell'indice ma non nel DB")
            else:
                logger.info(f"⚠️ Nessuna query simile trovata (distanza minima {distances[0][0]} > soglia {MAX_ACCEPTABLE_DISTANCE})")
        else:
            logger.info("⚠️ Indice FAISS vuoto o non inizializzato")

        return None
    except Exception as e:
        logger.error(f"Errore nel recupero della query dalla cache: {e}")
        return None


def save_query_to_cache(domanda, query_sql):
    """
    Salva una nuova query nella cache o aggiorna una esistente.

    Args:
        domanda: La domanda dell'utente
        query_sql: La query SQL generata

    Returns:
        True se l'operazione è riuscita, False altrimenti
    """
    try:
        # Sanitizza la domanda e la query
        domanda = domanda.strip()
        query_sql = query_sql.strip()

        if not domanda or not query_sql:
            logger.warning("Tentativo di salvare una domanda o query vuota.")
            return False

        # Carica il modello di embedding se non è già caricato
        if model is None:
            load_embedding_model()

        # Calcola l'embedding della domanda
        embedding = model.encode([domanda])[0]

        # Ottieni l'hash della struttura del database corrente
        from db_schema import get_db_structure_hash
        db_hash = get_db_structure_hash() or ""

        # Salva o aggiorna la query nel database
        session = Session()

        try:
            # Prima verifichiamo se esiste già questa domanda
            existing_entry = session.query(QueryCache).filter_by(domanda=domanda).first()

            if existing_entry:
                # Aggiorniamo l'entry esistente
                existing_entry.query_sql = query_sql
                existing_entry.db_hash = db_hash
                session.commit()
                logger.info(f"Query aggiornata per '{domanda}'")
            else:
                # Creiamo una nuova entry
                cache_entry = QueryCache(
                    domanda=domanda,
                    embedding=','.join(map(str, embedding)),
                    query_sql=query_sql,
                    db_hash=db_hash
                )
                session.add(cache_entry)
                session.commit()
                logger.info(f"Nuova query salvata per '{domanda}'")

            # Aggiorna l'indice FAISS
            rebuild_faiss_index()

            return True
        except IntegrityError:
            session.rollback()
            # Se abbiamo un errore di integrità, proviamo ad aggiornare
            try:
                existing_entry = session.query(QueryCache).filter_by(domanda=domanda).first()
                if existing_entry:
                    existing_entry.query_sql = query_sql
                    existing_entry.db_hash = db_hash
                    session.commit()
                    logger.info(f"Query aggiornata per '{domanda}' dopo errore di integrità")
                    rebuild_faiss_index()
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


def delete_cached_query(domanda):
    """
    Elimina una query dalla cache.

    Args:
        domanda: La domanda da eliminare

    Returns:
        True se l'operazione è riuscita, False altrimenti
    """
    try:
        session = Session()
        cache_entry = session.query(QueryCache).filter_by(domanda=domanda).first()

        if cache_entry:
            session.delete(cache_entry)
            session.commit()
            session.close()

            # Aggiorna l'indice FAISS
            rebuild_faiss_index()

            logger.info(f"Query eliminata per '{domanda}'")
            return True
        else:
            session.close()
            logger.warning(f"Nessuna query trovata per '{domanda}'")
            return False
    except Exception as e:
        logger.error(f"Errore nell'eliminazione della query dalla cache: {e}")
        return False


# Precarica il modello di embedding all'avvio del modulo
try:
    load_embedding_model()
except Exception as e:
    logger.error(f"Errore nel caricamento iniziale del modello: {e}")
