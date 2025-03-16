import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sshtunnel import SSHTunnelForwarder
import paramiko
from sqlalchemy import create_engine
import traceback
import io
from query_ai import generate_sql_query, process_query_results
from db_schema import get_db_schema
import logging
from database import create_db

# Configura il logging per vedere gli errori nel container
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ✅ Assicuriamoci che il database sia pronto all'avvio dell'app
create_db()


class SSHConfig(BaseModel):
    ssh_host: str
    ssh_user: str
    ssh_key: str


class DBConfig(BaseModel):
    host: str
    port: str
    user: str
    password: str
    database: str


class QueryRequest(BaseModel):
    domanda: str
    openai_api_key: str
    ssh_config: SSHConfig
    db_config: DBConfig
    force_no_cache: bool = False


class RefreshRequest(BaseModel):
    ssh_config: SSHConfig
    db_config: DBConfig


def create_ssh_tunnel(ssh_host, ssh_user, ssh_key, db_host, db_port):
    """Crea un tunnel SSH per connettersi al database remoto e ritorna l'oggetto server."""
    try:
        logger.info(f"🔌 Creazione del tunnel SSH verso {ssh_host} per connettersi a {db_host}:{db_port}")

        # Creazione della chiave privata corretta
        pkey = paramiko.RSAKey(file_obj=io.StringIO(ssh_key))

        server = SSHTunnelForwarder(
            (ssh_host, 22),
            ssh_username=ssh_user,
            ssh_pkey=pkey,
            remote_bind_address=(db_host, int(db_port)),
            local_bind_address=('127.0.0.1', 5433)
        )
        server.start()
        logger.info("✅ Tunnel SSH creato con successo!")
        return server
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

        # Crea il tunnel SSH
        ssh_tunnel = create_ssh_tunnel(
            request.ssh_config.ssh_host,
            request.ssh_config.ssh_user,
            request.ssh_config.ssh_key,
            request.db_config.host,
            request.db_config.port
        )

        # Connessione al database
        db_url = f"postgresql://{request.db_config.user}:{request.db_config.password}@127.0.0.1:5433/{request.db_config.database}"
        engine = create_engine(db_url)

        # Forza la scansione della struttura
        db_schema = get_db_schema(engine, force_refresh=True)

        # Chiude il tunnel SSH
        ssh_tunnel.stop()
        logger.info("✅ Riscansione completata")

        return {"status": "success", "schema": db_schema}

    except Exception as e:
        logger.error(f"❌ ERRORE: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Errore durante la riscansione: {str(e)}")


@app.post("/query")
def query_database(request: QueryRequest):
    """Gestisce la query AI attraverso il tunnel SSH verso PostgreSQL."""
    try:
        logger.info(f"📥 Ricevuta richiesta: {request.domanda}")

        # Crea il tunnel SSH
        ssh_tunnel = create_ssh_tunnel(
            request.ssh_config.ssh_host,
            request.ssh_config.ssh_user,
            request.ssh_config.ssh_key,
            request.db_config.host,
            request.db_config.port
        )

        # Configura la connessione al database
        db_url = f"postgresql://{request.db_config.user}:{request.db_config.password}@127.0.0.1:5433/{request.db_config.database}"
        logger.info(f"🔗 Connessione a PostgreSQL: {db_url}")

        engine = create_engine(db_url)

        # Recupera la struttura del database
        logger.info("📊 Provo recupero struttura db")
        db_schema = get_db_schema(engine)
        logger.info(f"📊 Struttura del database recuperata: {db_schema.keys()}")

        use_cache = not request.force_no_cache  # Se `force_no_cache` è True, ignoriamo la cache

        # Genera la query SQL con AI
        sql_query, cache_used = generate_sql_query(request.domanda, db_schema, request.openai_api_key, use_cache)
        logger.info(f"📝 Query SQL generata dall'AI: {sql_query}")

        # Esegue la query e ottiene il risultato
        risposta = process_query_results(engine, sql_query, request.domanda, request.openai_api_key)
        logger.info("✅ Query eseguita con successo!")

        # Chiude il tunnel SSH
        ssh_tunnel.stop()
        logger.info("🔌 Tunnel SSH chiuso.")

        risposta["query_sql"] = sql_query
        risposta["cache_used"] = cache_used

        return risposta

    except Exception as e:
        logger.error(f"❌ ERRORE: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
