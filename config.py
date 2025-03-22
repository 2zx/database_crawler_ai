"""
Configurazioni globali dell'applicazione.
Centralizza i percorsi e le impostazioni principali.
"""
import os

# Percorsi base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
CHARTS_DIR = os.path.join(EXPORTS_DIR, "charts")

# Percorso del database e cache
DB_PATH = os.path.join(CACHE_DIR, "query_cache.db")
DB_URL = f"sqlite:///{DB_PATH}"
HINT_DB_PATH = os.path.join(CACHE_DIR, "hint_store.db")
HINT_DB_URL = f"sqlite:///{HINT_DB_PATH}"
EMBEDDINGS_PATH = os.path.join(CACHE_DIR, "embeddings")
HINTS_FILE = os.path.join(CACHE_DIR, "hints.json")
DB_SCHEMA_CACHE_PATH = os.path.join(CACHE_DIR, "db_schema.json")

# Creazione automatica delle directory necessarie
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)
os.makedirs(CHARTS_DIR, exist_ok=True)
os.makedirs(EMBEDDINGS_PATH, exist_ok=True)

# Configurazioni server
BACKEND_HOST = "0.0.0.0"
BACKEND_PORT = 8000
FRONTEND_PORT = 8501
