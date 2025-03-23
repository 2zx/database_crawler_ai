import json
import os
import logging
from sqlalchemy import inspect  # type: ignore
import hashlib
from config import DB_SCHEMA_CACHE_PATH

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

        ignore_prefixes = [
            "base_",
            "mail_",
            "ir_",
            "wkf",
            "printing_",
            "cleanup_",
            "mis_report",
            "tags_",
            "tmp_",
            "queue_"
        ]

        ignore_contains = [
            "config",
            "settings",
            "report",
            "wizard"
        ]

        # Verifica se la tabella ha un prefisso da ignorare
        should_ignore_p = any(table_name.startswith(prefix) for prefix in ignore_prefixes)
        should_ignore_c = any(prefix in table_name for prefix in ignore_contains)
        should_ignore_s = table_name.endswith("_rel")

        # Salta questa tabella se ha un prefisso da ignorare
        if should_ignore_p or should_ignore_c or should_ignore_s:
            logger.info(f"⏭️ Ignoro tabella {table_name}")
            continue

        # TMP
        # Definiamo le parole chiave di interesse
        keywords_of_interest = ["partner", "product", "invoice", "sale", "purchase",
                                "stock", "account_analytic_account", "country", "company",
                                "mrp", "maintenance", "fleet", "jit40", "hr"]

        # Verifichiamo se la tabella NON contiene nessuna delle parole chiave
        if not any(keyword in table_name for keyword in keywords_of_interest):
            logger.info(f"⏭️ Ignoro tabella {table_name}")
            continue

        logger.info(f"📊 Ispeziono tabella {table_name}")
        columns = inspector.get_columns(table_name)
        foreign_keys = inspector.get_foreign_keys(table_name)
        #  indexes = inspector.get_indexes(table_name)  # ✅ Ora recuperiamo anche gli indici

        ignore_columns = ["create_uid", "write_uid", "create_date", "write_date"]

        schema_info[table_name] = {
            "cols": {
                col["name"]: {
                    #  "type": str(col["type"]),  # ✅ Salviamo il tipo di dato
                    "comment": col.get("comment", "")  # ✅ Recuperiamo i commenti
                }
                for col in columns if col["name"] not in ignore_columns
            },
            "fk": {
                fk["constrained_columns"][0]: fk["referred_table"]
                for fk in foreign_keys
                if fk["constrained_columns"][0] not in ignore_columns
            },
            #  "indexes": {idx["name"]: idx["column_names"] for idx in indexes if idx["name"] not in ignore_columns}  # ✅ indici
        }

    schema_info = clean_db_schema(schema_info)

    # 🔥 Salva la struttura nel file di cache
    with open(DB_SCHEMA_CACHE_PATH, "w") as file:
        json.dump(schema_info, file)

    logger.info("✅ Struttura del database salvata su file")
    return schema_info


def clean_db_schema(db_schema):
    """
    Post-processa il JSON dello schema del database:
    1. Elimina le foreign key che fanno riferimento a tabelle non presenti nello schema
    2. Rimuove i commenti vulli (null o stringa vuota)

    Args:
        db_schema (dict): Lo schema del database caricato dal JSON

    Returns:
        dict: Lo schema pulito
    """
    # Ottieni l'insieme di tutte le tabelle presenti nello schema
    available_tables = set(db_schema.keys())

    # Per ogni tabella
    for table_name, table_data in db_schema.items():
        # Pulizia delle foreign key
        if "fk" in table_data:
            # Crea un nuovo dizionario con solo le fk che puntano a tabelle esistenti
            valid_fk = {}

            for fk_column, referenced_table in table_data["fk"].items():
                if referenced_table in available_tables:
                    valid_fk[fk_column] = referenced_table

            # Sostituisci le foreign key originali con quelle valide
            if valid_fk:
                table_data["fk"] = valid_fk
            else:
                # Se non ci sono foreign key valide, rimuovi completamente la chiave 'fk'
                table_data.pop("fk", None)

        # Pulizia dei commenti vuoti nelle colonne
        if "cols" in table_data:
            for col_name, col_info in table_data["cols"].items():
                # Se la colonna ha una struttura con "type" e "comment"
                if isinstance(col_info, dict) and "comment" in col_info:
                    # Rimuovi i commenti nulli o vuoti
                    if col_info["comment"] is None or col_info["comment"] == "":
                        col_info.pop("comment", None)

    return db_schema


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
