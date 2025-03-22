import sqlite3
import numpy as np  # type: ignore
import faiss  # type: ignore
from sentence_transformers import SentenceTransformer  # type: ignore
import database
from db_schema import get_db_structure_hash
import logging

# Configura il logging per vedere gli errori nel container
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ Carichiamo un modello NLP leggero
model = SentenceTransformer("all-MiniLM-L6-v2")  # 🔥 Modello leggero ed efficiente


def encode_embedding(embedding):
    """Converte un vettore numpy in formato binario per salvarlo su SQLite."""
    return embedding.astype(np.float32).tobytes()


def decode_embedding(embedding_blob):
    """Converte un embedding binario in numpy array."""
    return np.frombuffer(embedding_blob, dtype=np.float32)


def get_cached_query(domanda):
    """
    Cerca una domanda simile nella cache usando FAISS per il confronto vettoriale.
    """
    domanda_vec = model.encode([domanda])[0]  # 🔹 Creiamo l'embedding della domanda
    current_db_hash = get_db_structure_hash()  # 🔹 Recuperiamo l'hash attuale del database

    conn = sqlite3.connect(database.DB_PATH)
    cursor = conn.cursor()
    # ✅ Selezioniamo solo le domande con lo stesso `db_hash`
    cursor.execute("""
        SELECT domanda, query_sql, embedding
        FROM query_cache
        WHERE db_hash = ?
    """, (current_db_hash,))
    cached_queries = cursor.fetchall()
    conn.close()

    if not cached_queries:
        return None  # 🔹 Nessuna query salvata, procediamo con OpenAI

    # 🔍 Estraiamo gli embedding salvati
    embeddings = np.array([decode_embedding(row[2]) for row in cached_queries], dtype=np.float32)

    # ✅ Creiamo un indice FAISS per cercare la domanda più simile
    index = faiss.IndexFlatL2(embeddings.shape[1])  # L2 = distanza euclidea
    index.add(embeddings)

    # ✅ Troviamo la domanda più simile
    score, indices = index.search(np.array([domanda_vec], dtype=np.float32), 1)

    best_match_idx = indices[0][0]
    best_match_score = score[0][0]

    if best_match_score < 0.2:  # 🔥 Se è abbastanza simile, la riutilizziamo

        logger.info(f"✅ utilizzo di query on cache con somiglianza score {best_match_score}")
        return cached_queries[best_match_idx][1]  # ✅ Ritorniamo la query SQL salvata

    logger.info("✅ nulla in cache generiamo una nuova query")
    return None  # 🔹 Se la somiglianza è bassa, generiamo una nuova query


def save_query_to_cache(domanda, query_sql):
    """
    Salva una nuova domanda e query nella cache.
    """
    domanda_vec = model.encode([domanda])[0]  # 🔹 Creiamo l'embedding della domanda

    db_hash = get_db_structure_hash()  # 🔹 Recuperiamo l'hash attuale del database

    conn = sqlite3.connect(database.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO query_cache (domanda, query_sql, db_hash, embedding)
        VALUES (?, ?, ?, ?)
    """, (domanda, query_sql, db_hash, domanda_vec.astype(np.float32).tobytes()))
    conn.commit()
    conn.close()

    logger.info(f"✅ inserita nuova entry in cache {domanda} {query_sql}")
