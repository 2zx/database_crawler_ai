"""
Endpoint per la gestione dello schema del database.
"""
import traceback
from fastapi import APIRouter, HTTPException  # type: ignore
from backend.api.models import RefreshRequest, ConnectionTestRequest, AvailableModelsResponse
from backend.core.connection import ConnectionManager
from backend.core.db_schema import get_db_schema
from backend.utils.logging import get_logger

logger = get_logger(__name__)

# Inizializza il router
router = APIRouter(tags=["schema"])


@router.post("/refresh_schema")
def refresh_db_schema(request: RefreshRequest):
    """
    Permette al frontend di forzare una nuova scansione della struttura del database.

    Args:
        request (RefreshRequest): Dati di configurazione

    Returns:
        dict: Stato dell'operazione e schema del database
    """
    ssh_tunnel = None

    try:
        logger.info("🔄 Forzata nuova scansione del database...")

        if request.ssh_config.use_ssh:
            logger.info("🔌 Tunnel SSH abilitato")

            # Crea il tunnel SSH
            ssh_tunnel, local_port = ConnectionManager.create_ssh_tunnel(
                request.ssh_config.ssh_host,
                request.ssh_config.ssh_user,
                request.ssh_config.ssh_key,
                request.db_config.host,
                request.db_config.port,
                request.db_config.db_type
            )
        else:
            local_port = None

        # Crea la connessione al database
        engine = ConnectionManager.create_db_engine(
            request.db_config.__dict__,
            local_port
        )

        # Forza la scansione della struttura
        db_schema = get_db_schema(engine, request.db_config.db_type, force_refresh=True)

        logger.info("✅ Riscansione completata")

        return {"status": "success", "schema": db_schema}

    except Exception as e:
        logger.error(f"❌ ERRORE: {traceback.format_exc()}")
        # Assicuriamoci di chiudere il tunnel SSH se esiste
        if 'ssh_tunnel' in locals() and ssh_tunnel:
            ssh_tunnel.stop()
            logger.info("🔌 Tunnel SSH chiuso dopo errore.")
        raise HTTPException(status_code=500, detail=f"Errore durante la riscansione: {str(e)}")
    finally:
        # Chiudiamo il tunnel SSH se è stato aperto
        if 'ssh_tunnel' in locals() and ssh_tunnel:
            ssh_tunnel.stop()
            logger.info("🔌 Tunnel SSH chiuso")


@router.post("/test_connection")
def test_connection(request: ConnectionTestRequest):
    """
    Testa la connessione SSH e al database.
    Restituisce lo stato di entrambe le connessioni.

    Args:
        request (ConnectionTestRequest): Dati di configurazione

    Returns:
        dict: Stato delle connessioni SSH e database
    """
    return ConnectionManager.test_connection(
        request.ssh_config.__dict__,
        request.db_config.__dict__
    )


@router.get("/available_models")
def get_available_models() -> AvailableModelsResponse:
    """
    Restituisce l'elenco dei modelli disponibili per ciascun provider LLM.

    Returns:
        dict: Modelli disponibili per provider
    """
    return {
        "openai": [
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "description": "Modello economico e veloce"},
            {"id": "gpt-4o", "name": "GPT-4o", "description": "Modello più potente con supporto multimodale"},
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "description": "Buon rapporto qualità-prezzo"}
        ],
        "claude": [
            {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku",
             "description": "Modello veloce ed economico"},
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet",
             "description": "Bilanciato per performance e costo"},
            {"id": "claude-3-7-sonnet-20250224", "name": "Claude 3.7 Sonnet",
             "description": "Modello più potente"}
        ],
        "deepseek": [
            {"id": "deepseek-chat", "name": "DeepSeek Chat", "description": "Modello di chat generale"},
            {"id": "deepseek-coder", "name": "DeepSeek Coder", "description": "Specializzato per codice"}
        ],
        "gemini": [
            {"id": "gemini-2.5-pro-preview-03-25", "name": "Gemini 2.5 Pro",
             "description": "Ragionamento avanzato, comprensione multimodale, ampia finestra di contesto"},
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "description": "Modello veloce ed economico"},
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "description": "Modello avanzato con contesto più ampio"},
        ]
    }
