import sqlite3
import os

DB_PATH = "query_cache.db"


def create_db():
    """
    Crea il database SQLite e la tabella di cache delle query se non esistono.
    """
    conn = sqlite3.connect(DB_PATH)
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
    # ✅ Creiamo un indice su `db_hash` per velocizzare la ricerca
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_db_hash ON query_cache(db_hash);")

    conn.commit()
    conn.close()


def get_db_connection():
    """
    Ritorna una connessione aperta a SQLite.
    """
    return sqlite3.connect(DB_PATH)


# ✅ Assicuriamoci che il database sia pronto all'avvio
if not os.path.exists(DB_PATH):
    print("⚠️ Database non trovato, lo creo ora...")
    create_db()
else:
    print("✅ Database SQLite già esistente.")
