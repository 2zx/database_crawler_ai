import json
import os
import logging
from sqlalchemy import inspect  # type: ignore
import hashlib
from config import DB_SCHEMA_CACHE_PATH

logger = logging.getLogger(__name__)


def get_db_schema(engine, db_type, force_refresh=False):
    """
    Recupera la struttura del database: tabelle, colonne, chiavi esterne, indici e commenti.
    Usa la cache salvata su file per evitare richieste ripetute al DB.
    Supporta sia PostgreSQL che SQL Server.

    :param engine: Connessione al database
    :param force_refresh: Se True, riscanza il database ignorando la cache
    :return: Dizionario con la struttura del database
    """
    if not force_refresh and os.path.exists(DB_SCHEMA_CACHE_PATH):
        logger.info("📄 Carico la struttura del database dalla cache")
        with open(DB_SCHEMA_CACHE_PATH, "r") as file:
            cache_data = json.load(file)
            if isinstance(cache_data, dict) and db_type in cache_data:
                return cache_data[db_type]
            else:
                # Retrocompatibilità: il file contiene solo una struttura, non separata per db_type
                return cache_data

    logger.info("🔍 Riscansione della struttura del database...")
    inspector = inspect(engine)
    schema_info = {}

    # Determina il tipo di database
    db_type = engine.dialect.name
    logger.info(f"🔍 Tipo di database rilevato: {db_type}")

    table_schema = None
    if db_type == "mssql":
        # Per SQL Server, ottieni anche lo schema delle tabelle
        try:
            # Prova a ottenere tabelle solo dal schema 'dbo' (predefinito)
            table_schema = 'dbo'
            table_names = inspector.get_table_names(schema=table_schema)
        except Exception:
            # Se fallisce, ottieni tutte le tabelle
            table_names = inspector.get_table_names()
            table_schema = None
    else:
        # Per PostgreSQL
        table_names = inspector.get_table_names()

    for table_name in table_names:

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
        ] if db_type == "postgresql" else [
        ]

        ignore_contains = [
            "config",
            "settings",
            "report",
            "wizard",
        ] if db_type == "postgresql" else [
            "FERMIPRODUZIONE"
        ]

        # Verifica se la tabella ha un prefisso da ignorare
        should_ignore_p = any(table_name.startswith(prefix)
                              for prefix in ignore_prefixes)
        should_ignore_c = any(
            prefix in table_name for prefix in ignore_contains)
        should_ignore_s = table_name.endswith("_rel")

        # Salta questa tabella se ha un prefisso da ignorare
        if should_ignore_p or should_ignore_c or should_ignore_s:
            logger.info(f"⏭️ Ignoro tabella {table_name}")
            continue

        # TMP # TMP
        # Definiamo le parole chiave di interesse (espansa per includere termini SQL Server comuni)
        keywords_of_interest = [
            "partner", "product", "invoice", "sale", "purchase",
            "stock", "account", "country", "company",
            "mrp", "maintenance", "fleet", "hr", "itinerary"
        ] if db_type == "postgresql" else [
            "produzione", "clienti", "articoli", "clientiarticoli", "allarmi"
        ]

        # Verifichiamo se la tabella NON contiene nessuna delle parole chiave
        if not any(keyword.lower() in table_name.lower() for keyword in keywords_of_interest):
            logger.info(f"⏭️ Ignoro tabella {table_name}")
            continue

        logger.info(f"📊 Ispeziono tabella {table_name}")

        # Ottieni colonne e chiavi in base al tipo di database
        if db_type == "mssql" and table_schema:
            columns = inspector.get_columns(table_name, schema=table_schema)
            foreign_keys = inspector.get_foreign_keys(
                table_name, schema=table_schema)
        else:
            columns = inspector.get_columns(table_name)
            foreign_keys = inspector.get_foreign_keys(table_name)

        ignore_columns = [
            "create_uid", "write_uid",
            "create_date", "write_date", "id", "sequence"
        ] if db_type == "postgresql" else []

        # Adattamento per gestire le differenze nei metadati tra PostgreSQL e SQL Server
        table_cols = {}
        for col in columns:
            if col["name"] not in ignore_columns:
                col_info = {}

                # Gestisci i commenti diversamente tra DB
                if db_type == "mssql":
                    # SQL Server non espone direttamente i commenti, possiamo aggiungerli manualmente se necessario
                    pass
                else:
                    # PostgreSQL
                    if col.get("comment", "") and col.get("comment", "").lower() != snake_to_label(col["name"]).lower():
                        # logger.info(f"⏭️ {col.get('comment', '').lower()} -- {snake_to_label(col['name']).lower()}")
                        col_info["comment"] = col.get("comment", "")

                table_cols[col["name"]] = col_info

        # Adattamento per le chiavi esterne
        table_fk = {}
        for fk in foreign_keys:
            if fk["constrained_columns"] and fk["constrained_columns"][0] not in ignore_columns:
                table_fk[fk["constrained_columns"][0]] = fk["referred_table"]

        schema_info[table_name] = {
            "cols": table_cols,
            "fk": table_fk
        }

    cache_data = get_cached_db_schema()
    cache_data[db_type] = clean_db_schema(schema_info)

    logger.info(f"chiavi {cache_data.keys()}")

    with open(DB_SCHEMA_CACHE_PATH, "w") as file:
        json.dump(cache_data, file, indent=2)

        logger.info("✅ Struttura del database salvata su file")
        return schema_info


def snake_to_label(snake_str):
    parts = snake_str.split('_')
    # Rimuove "id" se è l'ultimo elemento
    if parts[-1] == 'id':
        parts = parts[:-1]
    # Capitalizza solo il primo termine, unisci con spazio
    return ' '.join(parts)


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

    # Se lo schema è vuoto, non fare nulla
    if not db_schema:
        return {}

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


def handle_db_connection_error(e, db_type):
    """
    Gestisce gli errori di connessione al database in base al tipo di database.
    Fornisce messaggi di errore più specifici e suggerimenti per la risoluzione.

    Args:
        e (Exception): L'eccezione catturata
        db_type (str): Il tipo di database ('postgresql' o 'sqlserver')

    Returns:
        str: Messaggio di errore formattato con suggerimenti
    """
    error_str = str(e)

    if db_type == "sqlserver":
        # Errori comuni SQL Server
        if "Login failed for user" in error_str:
            return "❌ Errore di autenticazione SQL Server: username o password non validi."
        elif "TCP Provider: No connection could be made" in error_str:
            return (
                "❌ Impossibile connettersi al server SQL Server. Verifica che il server sia in esecuzione"
                " e raggiungibile attraverso il tunnel SSH."
            )
        elif "Database '" in error_str and "' not found" in error_str:
            return "❌ Database SQL Server non trovato. Verifica il nome del database."
        elif "SSL Provider: The certificate chain was issued by an authority that is not trusted" in error_str:
            return "❌ Problema di certificato SSL con SQL Server. Potresti dover configurare la connessione per non usare SSL."
    else:
        # Errori comuni PostgreSQL
        if "password authentication failed" in error_str:
            return "❌ Errore di autenticazione PostgreSQL: username o password non validi."
        elif "could not connect to server" in error_str:
            return (
                "❌ Impossibile connettersi al server PostgreSQL. Verifica che il server sia in esecuzione"
                " e raggiungibile attraverso il tunnel SSH."
            )
        elif "database" in error_str and "does not exist" in error_str:
            return "❌ Database PostgreSQL non trovato. Verifica il nome del database."

    # Errore generico
    return f"❌ Errore di connessione al database {db_type}: {error_str}"
