"""
Endpoint per la gestione delle query in linguaggio naturale.
"""
import asyncio
import threading
import traceback
import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks  # type: ignore
from backend.api.models import QueryRequest
from backend.core.connection import ConnectionManager
from backend.core.db_schema import get_db_schema
from backend.core.query_generator import generate_query_with_retry, process_query_results, generate_related_questions
from backend.db.query_cache import QueryCacheManager
from backend.utils.logging import get_logger

logger = get_logger(__name__)

# Inizializza il router
router = APIRouter(tags=["query"])

# Dizionario per tenere traccia dei progressi delle query
# Chiave: ID della query, Valore: dizionario con stato e dettagli
query_progress = {}

# Inizializza il gestore della cache
query_cache_manager = QueryCacheManager()


@router.post("/query")
async def query_database(request: QueryRequest, background_tasks: BackgroundTasks):
    """
    Gestisce la query AI attraverso il tunnel SSH verso il database.

    Args:
        request: Richiesta contenente domanda, configurazioni LLM, SSH e DB
        background_tasks: Gestore per task in background

    Returns:
        dict: ID della query e stato iniziale
    """
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
    """
    Esegue la query in background e aggiorna lo stato.

    Args:
        query_id (str): ID univoco della query
        request_data (QueryRequest): Dati della richiesta
    """
    ssh_tunnel = None

    try:
        # Inizializza lo stato della query
        query_progress[query_id] = {
            "status": "starting",
            "progress": 0,
            "message": "Inizializzazione della richiesta...",
            "step": "init",
            "domanda": request_data.domanda,  # Salva la domanda originale
            "llm_config": {  # Salva la configurazione LLM
                "provider": request_data.llm_config.provider,
                "api_key": request_data.llm_config.api_key,
                "model": request_data.llm_config.model
            }
        }

        # Aggiorna stato: inizializzazione
        query_progress[query_id].update({
            "status": "starting",
            "progress": 10,
            "message": "Inizializzazione della richiesta...",
            "step": "init"
        })

        logger.info(f"📥 Ricevuta richiesta: {request_data.domanda}")
        logger.info(f"📥 Provider LLM: {request_data.llm_config.provider}")

        # Loghiamo se stiamo forzando l'ignore cache
        if request_data.force_no_cache:
            logger.info("⚠️ Forzata rigenerazione query SQL (ignorata cache)")

        # Gestione del tunnel SSH se richiesto
        if request_data.ssh_config.use_ssh:
            logger.info("🔌 Tunnel SSH abilitato")

            # Aggiorna stato: apertura tunnel SSH
            query_progress[query_id].update({
                "status": "connecting",
                "progress": 20,
                "message": "Apertura connessione al database...",
                "step": "ssh_tunnel"
            })

            # Crea il tunnel SSH
            ssh_tunnel, local_port = ConnectionManager.create_ssh_tunnel(
                request_data.ssh_config.ssh_host,
                request_data.ssh_config.ssh_user,
                request_data.ssh_config.ssh_key,
                request_data.db_config.host,
                request_data.db_config.port,
                request_data.db_config.db_type
            )
        else:
            local_port = None

        # Crea la connessione al database
        engine = ConnectionManager.create_db_engine(
            request_data.db_config.__dict__,
            local_port
        )

        # Aggiorna stato: recupero schema db
        query_progress[query_id].update({
            "status": "schema",
            "progress": 30,
            "message": "Recupero struttura del database...",
            "step": "db_schema"
        })

        # Recupera la struttura del database
        logger.info("📊 Recupero struttura db")
        db_schema = get_db_schema(engine, request_data.db_config.db_type)
        logger.info(f"📊 Struttura del database recuperata: {len(db_schema.keys())} tabelle")

        # Aggiorna stato: generazione query SQL
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
            query_cache_manager,
            request_data.db_config.hint_category,
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
            # Aggiorna stato: query dalla cache
            query_progress[query_id].update({
                "status": "cache_hit",
                "progress": 50,
                "message": "Query SQL recuperata dalla cache!",
                "step": "cache_hit",
                "cache_used": True
            })
        else:
            logger.info(f"📝 Nuova query generata dall'AI dopo {attempts} tentativi: {sql_query}")
            # Aggiorna stato: query generata nuova
            query_progress[query_id].update({
                "status": "new_query",
                "progress": 50,
                "message": "Query SQL generata da zero",
                "step": "new_query",
                "cache_used": False
            })

        # Esegue la query e ottiene il risultato
        risposta = process_query_results(
            engine,
            sql_query,
            request_data.domanda,
            llm_config,
            query_progress[query_id]
        )

        if "error" in risposta:
            logger.error("❌ Query eseguita con errori")

            # Aggiorna stato: completato con errori
            query_progress[query_id].update({
                "status": "completed",
                "progress": 100,
                "message": "Analisi completata con errori",
                "step": "completed",
                "result": risposta
            })
        else:
            logger.info("✅ Query eseguita con successo!")

            # Aggiunge informazioni aggiuntive alla risposta
            risposta["query_sql"] = sql_query
            risposta["cache_used"] = cache_used
            risposta["llm_provider"] = request_data.llm_config.provider
            risposta["attempts"] = attempts  # Aggiungiamo il numero di tentativi

            # Genera automaticamente domande correlate
            related_questions = generate_related_questions(
                results=risposta,
                domanda=request_data.domanda,
                llm_config=llm_config,
                max_questions=5
            )
            logger.info(f"✅ Generate {len(related_questions)} domande correlate")
            risposta["related_questions"] = related_questions

            # Aggiorna stato: completato
            query_progress[query_id].update({
                "status": "completed",
                "progress": 100,
                "message": "Analisi completata con successo!",
                "step": "completed",
                "result": risposta
            })

    except Exception as e:
        logger.error(f"❌ ERRORE: {traceback.format_exc()}")

        # Aggiorna stato: errore
        query_progress[query_id].update({
            "status": "error",
            "progress": 100,
            "message": f"Errore nell'elaborazione: {str(e)}",
            "step": "error",
            "error": str(e),
            "error_traceback": traceback.format_exc()
        })

    finally:
        # Chiude il tunnel SSH
        if ssh_tunnel:
            ssh_tunnel.stop()
            logger.info("🔌 Tunnel SSH chiuso.")


@router.get("/query_status/{query_id}")
def check_query_status(query_id: str):
    """
    Restituisce lo stato corrente di una query in esecuzione.

    Args:
        query_id (str): ID della query

    Returns:
        dict: Stato corrente della query
    """
    if query_id not in query_progress:
        raise HTTPException(status_code=404, detail="Query ID non trovato")

    return query_progress[query_id]


@router.post("/related_questions/{query_id}")
async def get_related_questions(query_id: str, max_questions: int = 5):
    """
    Genera domande correlate basate sui risultati di una query precedente.

    Args:
        query_id (str): L'ID della query precedente
        max_questions (int): Numero massimo di domande da generare

    Returns:
        dict: Lista di domande correlate
    """
    try:
        # Verifica che la query esista e sia completata
        if query_id not in query_progress:
            raise HTTPException(status_code=404, detail="Query ID non trovato")

        query_status = query_progress[query_id]
        if query_status.get("status") != "completed":
            raise HTTPException(status_code=400, detail="La query non è ancora completata")

        # Ottieni i risultati e la domanda originale
        results = query_status.get("result", {})
        domanda = query_status.get("domanda", "")
        llm_config = query_status.get("llm_config", {})

        # Genera le domande correlate
        related_questions = generate_related_questions(
            results=results,
            domanda=domanda,
            llm_config=llm_config,
            max_questions=max_questions
        )

        return {"questions": related_questions}

    except HTTPException:
        # Rilancia le eccezioni HTTP
        raise
    except Exception as e:
        logger.error(f"❌ Errore nella generazione delle domande correlate: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")
