import threading
import uvicorn  # type: ignore
from fastapi import FastAPI, HTTPException, BackgroundTasks  # type: ignore
from pydantic import BaseModel  # type: ignore
from sshtunnel import SSHTunnelForwarder  # type: ignore
import paramiko  # type: ignore
from sqlalchemy import create_engine  # type: ignore
import traceback
import io
import asyncio
from query_ai import generate_query_with_retry, process_query_results
from db_schema import get_db_schema
import logging
from database import create_db
from hint_manager import (
    add_hint, update_hint, delete_hint, toggle_hint_status,
    get_all_hints, get_active_hints, get_hint_by_id,
    format_hints_for_prompt, export_hints_to_json, import_hints_from_json,
    get_all_categories, add_category, delete_category
)
from typing import Optional
import uuid

# Configura il logging per vedere gli errori nel container
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ✅ Assicuriamoci che il database sia pronto all'avvio dell'app
create_db()

# Dizionario per tenere traccia dei progressi delle query
# Chiave: ID della query, Valore: dizionario con stato e dettagli
query_progress = {}


class SSHConfig(BaseModel):
    ssh_host: str
    ssh_user: str
    ssh_key: str
    use_ssh: bool


class DBConfig(BaseModel):
    host: str
    port: str
    user: str
    password: str
    database: str
    db_type: str = "postgresql"  # postgresql o sqlserver
    hint_category: str = "generale"


class LLMConfig(BaseModel):
    provider: str
    api_key: str
    model: Optional[str] = None
    secret_key: Optional[str] = None  # Per Baidu ERNIE


class QueryRequest(BaseModel):
    domanda: str
    llm_config: LLMConfig
    ssh_config: SSHConfig
    db_config: DBConfig
    force_no_cache: bool = False


class RefreshRequest(BaseModel):
    ssh_config: SSHConfig
    db_config: DBConfig


class HintRequest(BaseModel):
    hint_text: str
    hint_category: str = "generale"


class HintUpdateRequest(BaseModel):
    hint_text: Optional[str] = None
    hint_category: Optional[str] = None
    active: Optional[int] = None


class CategoryRequest(BaseModel):
    name: str


class CategoryDeleteRequest(BaseModel):
    name: str
    replace_with: str = "generale"


def create_ssh_tunnel(ssh_host, ssh_user, ssh_key, db_host, db_port, db_type="postgresql"):
    """
    Crea un tunnel SSH per connettersi al database remoto e ritorna l'oggetto server.
    Supporta sia PostgreSQL che SQL Server.
    """
    try:
        logger.info(f"🔌 Creazione del tunnel SSH verso {ssh_host} per connettersi a {db_host}:{db_port} ({db_type})")

        # Creazione della chiave privata corretta
        pkey = paramiko.RSAKey(file_obj=io.StringIO(ssh_key))

        # Determina la porta locale in base al tipo di database per evitare conflitti
        local_port = 5433 if db_type == "postgresql" else 5434

        server = SSHTunnelForwarder(
            (ssh_host, 22),
            ssh_username=ssh_user,
            ssh_pkey=pkey,
            remote_bind_address=(db_host, int(db_port)),
            local_bind_address=('127.0.0.1', local_port)
        )
        server.start()
        logger.info(f"✅ Tunnel SSH creato con successo per {db_type} sulla porta locale {local_port}!")
        return server, local_port
    except Exception as e:
        logger.error(f"❌ Errore nel tunnel SSH: {e}")
        raise HTTPException(status_code=500, detail=f"Errore nel tunnel SSH: {str(e)}")


@app.post("/refresh_schema")
def refresh_db_schema(request: RefreshRequest):
    """
    Permette al frontend di forzare una nuova scansione della struttura del database.
    """
    try:
        logger.info("🔄 Forzata nuova scansione del database...")

        if request.ssh_config.use_ssh:
            logger.info("🔌 Tunnel SSH abilitato")

            # Crea il tunnel SSH
            ssh_tunnel, local_port = create_ssh_tunnel(
                request.ssh_config.ssh_host,
                request.ssh_config.ssh_user,
                request.ssh_config.ssh_key,
                request.db_config.host,
                request.db_config.port,
                request.db_config.db_type
            )

        # Connessione al database in base al tipo
        if request.db_config.db_type == "sqlserver":
            # Per SQL Server
            db_url = (
                f"mssql+pymssql://{request.db_config.user}:{request.db_config.password}"
                f"@127.0.0.1:{local_port}/{request.db_config.database}"
            )
            logger.info(f"🔗 Connessione a SQL Server: {db_url}")
        else:
            # Per PostgreSQL (default)
            db_url = (
                f"postgresql://{request.db_config.user}:{request.db_config.password}"
                f"@127.0.0.1:{local_port}/{request.db_config.database}"
            )
            logger.info(f"🔗 Connessione a PostgreSQL: {db_url}")

        engine = create_engine(db_url)

        # Forza la scansione della struttura
        db_schema = get_db_schema(engine, request.db_config.db_type, force_refresh=True)

        # Chiude il tunnel SSH
        ssh_tunnel.stop()
        logger.info("✅ Riscansione completata")

        return {"status": "success", "schema": db_schema}

    except Exception as e:
        logger.error(f"❌ ERRORE: {traceback.format_exc()}")
        # Assicuriamoci di chiudere il tunnel SSH se esiste
        try:
            if 'ssh_tunnel' in locals():
                ssh_tunnel.stop()
                logger.info("🔌 Tunnel SSH chiuso dopo errore.")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Errore durante la riscansione: {str(e)}")


# Endpoint per la gestione degli hint
@app.get("/hints")
def get_hints():
    """Recupera tutti gli hint."""
    return get_all_hints()


@app.get("/hints/active")
def get_hints_active(hint_category: str = ""):
    """Recupera solo gli hint attivi."""
    return get_active_hints(hint_category)


@app.get("/hints/{hint_id}")
def get_hint(hint_id: int):
    """Recupera un hint specifico."""
    hint = get_hint_by_id(hint_id)
    if hint:
        return hint
    raise HTTPException(status_code=404, detail="Hint non trovato")


@app.post("/hints")
def create_hint(request: HintRequest):
    """Crea un nuovo hint."""
    hint_id = add_hint(request.hint_text, request.hint_category)
    if hint_id:
        return {"status": "success", "id": hint_id}
    raise HTTPException(status_code=500, detail="Errore nella creazione dell'hint")


@app.put("/hints/{hint_id}")
def modify_hint(hint_id: int, request: HintUpdateRequest):
    """Aggiorna un hint esistente."""
    success = update_hint(
        hint_id,
        request.hint_text,
        request.hint_category,
        request.active
    )
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Hint non trovato o errore nell'aggiornamento")


@app.delete("/hints/{hint_id}")
def remove_hint(hint_id: int):
    """Elimina un hint."""
    success = delete_hint(hint_id)
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Hint non trovato o errore nell'eliminazione")


@app.put("/hints/{hint_id}/toggle")
def toggle_hint(hint_id: int):
    """Attiva o disattiva un hint."""
    success = toggle_hint_status(hint_id)
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Hint non trovato o errore nel cambio di stato")


@app.get("/hints/formatted")
def get_formatted_hints():
    """Recupera gli hint formattati per il prompt."""
    formatted = format_hints_for_prompt()
    return {"hints_formatted": formatted}


@app.post("/hints/export")
def export_hints():
    """Esporta gli hint in un file JSON."""
    success = export_hints_to_json()
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Errore nell'esportazione degli hint")


@app.post("/hints/import")
def import_hints():
    """Importa gli hint da un file JSON."""
    success = import_hints_from_json()
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Errore nell'importazione degli hint")


@app.get("/categories")
def get_categories():
    """Recupera tutte le categorie disponibili."""
    categories = get_all_categories()
    return {"categories": categories}


@app.post("/categories")
def create_category(request: CategoryRequest):
    """Crea una nuova categoria."""
    success = add_category(request.name)
    if success:
        return {"status": "success", "message": f"Categoria '{request.name}' creata"}
    else:
        raise HTTPException(status_code=400, detail=f"La categoria '{request.name}' esiste già")


@app.delete("/categories")
def remove_category(request: CategoryDeleteRequest):
    """Elimina una categoria e aggiorna gli hint associati."""
    if request.name == "generale":
        raise HTTPException(status_code=400, detail="Non è possibile eliminare la categoria 'generale'")

    affected_rows = delete_category(request.name, request.replace_with)
    if affected_rows >= 0:
        return {"status": "success", "affected_rows": affected_rows}
    else:
        raise HTTPException(status_code=500, detail="Errore nell'eliminazione della categoria")


@app.post("/query")
async def query_database(request: QueryRequest, background_tasks: BackgroundTasks):
    """Gestisce la query AI attraverso il tunnel SSH verso PostgreSQL."""
    try:
        # Genera un ID univoco per questa query
        query_id = str(uuid.uuid4())

        def run_in_background():
            asyncio.run(process_query_in_background(query_id, request))

        thread = threading.Thread(target=run_in_background)
        thread.start()

        # Restituisci immediatamente l'ID della query
        return {"query_id": query_id, "status": "processing"}

    except Exception as e:
        logger.error(f"❌ ERRORE: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


# Funzione di task in background che esegue la query e aggiorna lo stato
async def process_query_in_background(query_id, request_data):
    try:
        # Inizializza lo stato della query
        query_progress[query_id] = {
            "status": "starting",
            "progress": 0,
            "message": "Inizializzazione della richiesta...",
            "step": "init"
        }

        logger.info(f"📥 Ricevuta richiesta: {request_data.domanda}")
        logger.info(f"📥 Provider LLM: {request_data.llm_config.provider}")

        # Loghiamo se stiamo forzando l'ignore cache
        if request_data.force_no_cache:
            logger.info("⚠️ Forzata rigenerazione query SQL (ignorata cache)")

        if request_data.ssh_config.use_ssh:
            logger.info("🔌 Tunnel SSH abilitato")

            # Aggiorna lo stato: apertura tunnel SSH
            query_progress[query_id].update({
                "status": "connecting",
                "progress": 10,
                "message": "Apertura connessione al database...",
                "step": "ssh_tunnel"
            })

            # Crea il tunnel SSH
            ssh_tunnel, local_port = create_ssh_tunnel(
                request_data.ssh_config.ssh_host,
                request_data.ssh_config.ssh_user,
                request_data.ssh_config.ssh_key,
                request_data.db_config.host,
                request_data.db_config.port,
                request_data.db_config.db_type
            )

        # Configura la connessione al database in base al tipo
        if request_data.db_config.db_type == "sqlserver":
            # Per SQL Server
            db_url = (
                f"mssql+pymssql://{request_data.db_config.user}:{request_data.db_config.password}"
                f"@127.0.0.1:{local_port}/{request_data.db_config.database}"
            )
            logger.info(f"🔗 Connessione a SQL Server: {db_url}")
        else:
            # Per PostgreSQL (default)
            db_url = (
                f"postgresql://{request_data.db_config.user}:{request_data.db_config.password}"
                f"@127.0.0.1:{local_port}/{request_data.db_config.database}"
            )
            logger.info(f"🔗 Connessione a PostgreSQL: {db_url}")

        engine = create_engine(db_url)

        # Aggiorna lo stato: recupero schema db
        query_progress[query_id].update({
            "status": "schema",
            "progress": 20,
            "message": "Recupero struttura del database...",
            "step": "db_schema"
        })

        # Recupera la struttura del database
        logger.info("📊 Provo recupero struttura db")
        db_schema = get_db_schema(engine, request_data.db_config.db_type)
        logger.info(f"📊 Struttura del database recuperata: {db_schema.keys()}")

        # Aggiorna lo stato: generazione query SQL
        query_progress[query_id].update({
            "status": "generating",
            "progress": 40,
            "message": "Generazione query SQL con AI...",
            "step": "generate_sql"
        })

        # Se `force_no_cache` è True, ignoriamo la cache
        use_cache = not request_data.force_no_cache

        # Convertiamo la configurazione LLM in un dizionario
        llm_config = {
            "provider": request_data.llm_config.provider,
            "api_key": request_data.llm_config.api_key,
            "model": request_data.llm_config.model
        }

        # Aggiungiamo secret_key se presente (per Baidu ERNIE)
        if request_data.llm_config.secret_key:
            llm_config["secret_key"] = request_data.llm_config.secret_key

        # Genera la query SQL con AI, passando esplicitamente use_cache
        sql_query, cache_used, attempts = generate_query_with_retry(
            request_data.domanda,
            db_schema,
            llm_config,
            use_cache,
            engine,
            request_data.db_config.hint_category,
            5,
            progress_callback=lambda status, message, step, progress:
                query_progress[query_id].update({
                    "status": status,
                    "message": message,
                    "step": step,
                    "progress": progress
                })
        )

        if cache_used:
            logger.info("✅ Query recuperata dalla cache")
            # Aggiorna lo stato: query dalla cache
            query_progress[query_id].update({
                "status": "cache_hit",
                "progress": 50,
                "message": "Query SQL recuperata dalla cache!",
                "step": "cache_hit",
                "cache_used": True
            })
        else:
            logger.info(f"📝 Nuova query generata dall'AI dopo {attempts} tentativi: {sql_query}")
            # Aggiorna lo stato: query generata nuova
            query_progress[query_id].update({
                "status": "new_query",
                "progress": 50,
                "message": "Query SQL generata da zero",
                "step": "new_query",
                "cache_used": False
            })

        # Esegue la query e ottiene il risultato
        risposta = process_query_results(engine, sql_query, request_data.domanda, llm_config, query_progress[query_id])
        logger.info("✅ Query eseguita con successo!")

        # Aggiunge informazioni aggiuntive alla risposta
        risposta["query_sql"] = sql_query
        risposta["cache_used"] = cache_used
        risposta["llm_provider"] = request_data.llm_config.provider
        risposta["attempts"] = attempts  # Aggiungiamo il numero di tentativi

        # Chiude il tunnel SSH
        ssh_tunnel.stop()
        logger.info("🔌 Tunnel SSH chiuso.")

        # Aggiorna lo stato: completato
        query_progress[query_id].update({
            "status": "completed",
            "progress": 100,
            "message": "Analisi completata con successo!",
            "step": "completed",
            "result": risposta
        })

    except Exception as e:
        logger.error(f"❌ ERRORE: {traceback.format_exc()}")

        # Aggiorna lo stato: errore
        query_progress[query_id].update({
            "status": "error",
            "progress": 100,
            "message": f"Errore nell'elaborazione: {str(e)}",
            "step": "error",
            "error": str(e),
            "error_traceback": traceback.format_exc()
        })

        # Assicuriamoci di chiudere il tunnel SSH se esiste
        try:
            if 'ssh_tunnel' in locals():
                ssh_tunnel.stop()
                logger.info("🔌 Tunnel SSH chiuso dopo errore.")
        except Exception:
            pass


@app.get("/available_models")
def get_available_models():
    """
    Restituisce l'elenco dei modelli disponibili per ciascun provider LLM.
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
        "ernie": [
            {"id": "ernie-bot-4", "name": "ERNIE Bot 4", "description": "Modello avanzato di Baidu"},
            {"id": "ernie-bot", "name": "ERNIE Bot", "description": "Modello di base"}
        ]
    }


# Endpoint per verificare lo stato di una query in corso
@app.get("/query_status/{query_id}")
def check_query_status(query_id: str):
    """Restituisce lo stato corrente di una query in esecuzione."""
    if query_id not in query_progress:
        raise HTTPException(status_code=404, detail="Query ID non trovato")

    return query_progress[query_id]


@app.get("/")
def root():
    """
    Ritorna info basilari sull'API.
    """
    return {
        "app": "Database Crawler AI",
        "version": "2.0.0",
        "features": [
            "Multi LLM Support (OpenAI, Claude, DeepSeek, Baidu ERNIE)",
            "Query SQL in linguaggio naturale",
            "Cache intelligente delle query",
            "Sistema di hint per interpretazione dati",
            "Tunnel SSH per database remoti"
        ]
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
