import json
import os
import logging
from sqlalchemy import inspect

SCHEMA_FILE = "/app/db_schema.json"  # 🔥 Percorso del file di cache della struttura
logger = logging.getLogger(__name__)


def get_db_schema(engine, force_refresh=False):
    """
    Recupera la struttura del database: tabelle, colonne, chiavi esterne, indici e commenti.
    Usa la cache salvata su file per evitare richieste ripetute al DB.

    :param engine: Connessione al database
    :param force_refresh: Se True, riscanza il database ignorando la cache
    :return: Dizionario con la struttura del database
    """
    if not force_refresh and os.path.exists(SCHEMA_FILE):
        logger.info("📄 Carico la struttura del database dalla cache")
        with open(SCHEMA_FILE, "r") as file:
            return json.load(file)

    logger.info("🔍 Riscansione della struttura del database...")
    inspector = inspect(engine)
    schema_info = {}

    for table_name in inspector.get_table_names():
        if table_name.startswith("wizard_") or table_name.startswith("ir_"):
            continue  # Ignora le tabelle temporanee

        if not table_name.startswith("product") and not table_name.startswith("sale") and not "invoice" in table_name:
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
    with open(SCHEMA_FILE, "w") as file:
        json.dump(schema_info, file)

    logger.info("✅ Struttura del database salvata su file")
    return schema_info
