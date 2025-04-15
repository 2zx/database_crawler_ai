"""
Configurazioni globali dell'applicazione.
Centralizza i percorsi e le impostazioni principali.
"""
import os
from pathlib import Path

# Percorsi base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
CACHE_DIR = os.path.join(PARENT_DIR, "cache")
EXPORTS_DIR = os.path.join(PARENT_DIR, "exports")
CHARTS_DIR = os.path.join(PARENT_DIR, "charts")

# Percorso del database e cache
DB_PATH = os.path.join(CACHE_DIR, "query_cache.db")
DB_URL = f"sqlite:///{DB_PATH}"
HINT_DB_PATH = os.path.join(CACHE_DIR, "hint_store.db")
HINT_DB_URL = f"sqlite:///{HINT_DB_PATH}"
EMBEDDINGS_PATH = os.path.join(CACHE_DIR, "embeddings")
HINTS_FILE = os.path.join(CACHE_DIR, "hints.json")
DB_SCHEMA_CACHE_PATH = os.path.join(CACHE_DIR, "db_schema.json")
PROFILES_FILE = os.path.join(CACHE_DIR, "connection_profiles.json")

# Configurazioni server
BACKEND_HOST = "0.0.0.0"
BACKEND_PORT = 8000
FRONTEND_PORT = 8501

# Logger
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Default LLM configurations
DEFAULT_LLM_PROVIDER = "openai"
DEFAULT_LLM_MODELS = {
    "openai": "gpt-4o-mini",
    "claude": "claude-3-haiku-20240307",
    "deepseek": "deepseek-chat",
    "gemini": "gemini-pro"
}

# Costanti per la generazione di query
MAX_QUERY_ATTEMPTS = 9
MAX_TOKEN_DEFAULT = 1000
MAX_ACCEPTABLE_DISTANCE = 0.5  # Soglia di distanza massima per considerare due domande simili


# Creazione automatica delle directory necessarie
def ensure_directories():
    """Crea le directory necessarie se non esistono."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    os.makedirs(CHARTS_DIR, exist_ok=True)
    os.makedirs(EMBEDDINGS_PATH, exist_ok=True)

    # Crea un file .gitkeep per mantenere la directory charts anche se vuota
    Path(os.path.join(CHARTS_DIR, ".gitkeep")).touch(exist_ok=True)
