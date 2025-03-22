import json
import os
import logging
from sqlalchemy import inspect  # type: ignore
import hashlib

DB_SCHEMA_CACHE_PATH = "/app/db_schema.json"  # 🔥 Percorso del file di cache della struttura
logger = logging.getLogger(__name__)


def get_db_schema(engine, force_refresh=False):
    """
    Recupera la struttura del database: tabelle, colonne, chiavi esterne, indici e commenti.
    Usa la cache salvata su file per evitare richieste ripetute al DB.

    :param engine: Connessione al database
    :param force_refresh: Se True, riscanza il database ignorando la cache
    :return: Dizionario con la struttura del database
    """
    if not force_refresh and os.path.exists(DB_SCHEMA_CACHE_PATH):
        logger.info("📄 Carico la struttura del database dalla cache")
        with open(DB_SCHEMA_CACHE_PATH, "r") as file:
            return json.load(file)

    logger.info("🔍 Riscansione della struttura del database...")
    inspector = inspect(engine)
    schema_info = {}

    for table_name in inspector.get_table_names():
        if table_name.startswith("wizard_") or table_name.startswith("ir_"):
            continue  # Ignora le tabelle temporanee

        if not table_name.startswith("product") and not table_name.startswith("sale") and "invoice" not in table_name:
            continue

        logger.info(f"📊 Ispeziono tabella {table_name}")
        columns = inspector.get_columns(table_name)
        foreign_keys = inspector.get_foreign_keys(table_name)
        indexes = inspector.get_indexes(table_name)  # ✅ Ora recuperiamo anche gli indici

        schema_info[table_name] = {
            "columns": {
                col["name"]: {
                    "type": str(col["type"]),  # ✅ Salviamo il tipo di dato
                    "comment": col.get("comment", "")  # ✅ Recuperiamo i commenti
                }
                for col in columns
            },
            "foreign_keys": {
                fk["constrained_columns"][0]: fk["referred_table"] for fk in foreign_keys
            },
            "indexes": {idx["name"]: idx["column_names"] for idx in indexes}  # ✅ Salviamo gli indici
        }

    # 🔥 Salva la struttura nel file di cache
    with open(DB_SCHEMA_CACHE_PATH, "w") as file:
        json.dump(schema_info, file)

    logger.info("✅ Struttura del database salvata su file")
    return schema_info


def get_cached_db_schema():
    """
    Recupera la struttura del database dalla cache locale.
    """
    if not os.path.exists(DB_SCHEMA_CACHE_PATH):
        print("⚠️ Nessuna cache trovata per lo schema del database.")
        return None

    with open(DB_SCHEMA_CACHE_PATH, "r") as f:
        return json.load(f)


def get_db_structure_hash():
    """
    Genera un hash SHA256 basato sulla cache della struttura del database.
    Se la cache non esiste, restituisce None.
    """
    db_schema = get_cached_db_schema()
    if db_schema is None:
        return None  # ⚠️ Nessuna cache disponibile, dovremmo riscanalizzare

    # Convertiamo lo schema in JSON ordinato per garantire un hash stabile
    schema_str = json.dumps(db_schema, sort_keys=True)
    return hashlib.sha256(schema_str.encode()).hexdigest()
