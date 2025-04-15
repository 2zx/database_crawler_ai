"""
Punto di ingresso principale dell'applicazione.
Configura e avvia il server FastAPI.
"""
import uvicorn  # type: ignore
from fastapi import FastAPI  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from backend.api import router
from backend.utils.logging import setup_logging
from backend.config import BACKEND_HOST, BACKEND_PORT, ensure_directories
from backend.db.database import initialize_database
from backend.config import DB_PATH, HINT_DB_PATH

# Inizializza il logger
logger = setup_logging()

# Assicurati che le directory necessarie esistano
ensure_directories()

# Inizializza i database
initialize_database(DB_PATH)
initialize_database(HINT_DB_PATH)

# Crea l'app FastAPI
app = FastAPI(
    title="Database Crawler AI",
    description="API per interagire con database tramite linguaggio naturale",
    version="2.0.0"
)

# Configurazione CORS per permettere le richieste dal frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In produzione, limitare alle origini specifiche
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Includi tutti i router
app.include_router(router)


@app.get("/")
def root():
    """
    Ritorna info basilari sull'API.
    """
    return {
        "app": "Database Crawler AI",
        "version": "2.0.0",
        "features": [
            "Multi LLM Support (OpenAI, Claude, DeepSeek, Gemini)",
            "Query SQL in linguaggio naturale",
            "Cache intelligente delle query",
            "Sistema di hint per interpretazione dati",
            "Tunnel SSH per database remoti"
        ]
    }


if __name__ == "__main__":
    uvicorn.run(app, host=BACKEND_HOST, port=BACKEND_PORT)
