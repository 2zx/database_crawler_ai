"""
Gestione della connessione al database SQLite per la cache delle query e degli hint.
Fornisce funzioni per la creazione e l'accesso al database locale.
"""
import sqlite3
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def create_db(db_path):
    """
    Crea il database SQLite e la tabella di cache delle query se non esistono.

    Args:
        db_path (str): Percorso del file database SQLite
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS query_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domanda TEXT UNIQUE,
            query_sql TEXT,
            db_hash TEXT,
            embedding BLOB
        )
    """)
    # Creiamo un indice su `db_hash` per velocizzare la ricerca
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_db_hash ON query_cache(db_hash);")

    conn.commit()
    conn.close()
    logger.info(f"Database SQLite creato con successo: {db_path}")


def get_db_connection(db_path):
    """
    Ritorna una connessione aperta a SQLite.

    Args:
        db_path (str): Percorso del file database SQLite

    Returns:
        sqlite3.Connection: Oggetto connessione al database
    """
    return sqlite3.connect(db_path)


def initialize_database(db_path):
    """
    Inizializza il database assicurandosi che esista.

    Args:
        db_path (str): Percorso del file database SQLite

    Returns:
        bool: True se il database è stato inizializzato con successo
    """
    try:
        # Assicuriamoci che la directory esista
        Path(os.path.dirname(db_path)).mkdir(parents=True, exist_ok=True)

        if not os.path.exists(db_path):
            logger.info(f"⚠️ Database non trovato, lo creo ora: {db_path}")
            create_db(db_path)
        else:
            logger.info(f"✅ Database SQLite già esistente: {db_path}")

        return True
    except Exception as e:
        logger.error(f"❌ Errore nell'inizializzazione del database: {e}")
        return False
