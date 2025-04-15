"""
Gestisce l'analisi e il caching dello schema del database.
Supporta PostgreSQL e SQL Server.
"""
import json
import os
import hashlib
from sqlalchemy import inspect  # type: ignore[import]
from backend.utils.logging import get_logger
from backend.config import DB_SCHEMA_CACHE_PATH

logger = get_logger(__name__)


def snake_to_label(snake_str):
    """
    Converte uno snake_case in una stringa leggibile.

    Args:
        snake_str (str): Stringa in formato snake_case

    Returns:
        str: Stringa formattata per essere leggibile
    """
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


def get_db_schema(engine, db_type, force_refresh=False):
    """
    Recupera la struttura del database: tabelle, colonne, chiavi esterne, indici e commenti.
    Usa la cache salvata su file per evitare richieste ripetute al DB.
    Supporta sia PostgreSQL che SQL Server.

    Args:
        engine: Connessione SQLAlchemy al database
        db_type (str): Tipo di database ("postgresql" o "sqlserver")
        force_refresh (bool): Se True, riscanza il database ignorando la cache

    Returns:
        dict: Dizionario con la struttura del database
    """
    # Verifica se esiste una cache valida, a meno che force_refresh sia True
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

    # Log del tipo di database rilevato
    logger.info(f"🔍 Tipo di database rilevato: {db_type}")

    # Determina lo schema delle tabelle per SQL Server
    table_schema = None
    if db_type == "sqlserver" or db_type.startswith("mssql"):
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

    # Definisci i pattern per tabelle da ignorare
    ignore_prefixes = get_ignore_prefixes(db_type)
    ignore_contains = get_ignore_contains(db_type)
    keywords_of_interest = get_keywords_of_interest(db_type)

    # Scansiona le tabelle
    for table_name in table_names:
        # Verifica se la tabella dovrebbe essere ignorata
        if should_ignore_table(table_name, ignore_prefixes, ignore_contains):
            logger.info(f"⏭️ Ignoro tabella {table_name}")
            continue

        # Verifichiamo se la tabella NON contiene nessuna delle parole chiave
        if not any(keyword.lower() in table_name.lower() for keyword in keywords_of_interest):
            logger.info(f"⏭️ Ignoro tabella {table_name} (non contiene parole chiave di interesse)")
            continue

        logger.info(f"📊 Ispeziono tabella {table_name}")

        # Ottieni colonne e chiavi in base al tipo di database
        if db_type == "sqlserver" and table_schema:
            columns = inspector.get_columns(table_name, schema=table_schema)
            foreign_keys = inspector.get_foreign_keys(table_name, schema=table_schema)
        else:
            columns = inspector.get_columns(table_name)
            foreign_keys = inspector.get_foreign_keys(table_name)

        # Colonne da ignorare in ogni tabella
        ignore_columns = [
            "create_uid", "write_uid", "create_date", "write_date", "id", "sequence"
        ] if db_type == "postgresql" else []

        # Adattamento per gestire le differenze nei metadati tra PostgreSQL e SQL Server
        table_cols = {}
        for col in columns:
            if col["name"] not in ignore_columns:
                col_info = {}

                # Gestisci i commenti diversamente tra DB
                if db_type == "sqlserver":
                    # SQL Server non espone direttamente i commenti
                    pass
                else:
                    # PostgreSQL
                    if col.get("comment", "") and col.get("comment", "").lower() != snake_to_label(col["name"]).lower():
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

    # Aggiorna la cache
    cache_data = get_cached_db_schema() or {}
    cache_data[db_type] = clean_db_schema(schema_info)

    with open(DB_SCHEMA_CACHE_PATH, "w") as file:
        json.dump(cache_data, file, indent=2)

    logger.info("✅ Struttura del database salvata su file")
    return schema_info


def get_ignore_prefixes(db_type):
    """
    Restituisce i prefissi di tabelle da ignorare in base al tipo di database.

    Args:
        db_type (str): Tipo di database

    Returns:
        list: Lista di prefissi da ignorare
    """
    if db_type == "postgresql":
        return [
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
    else:
        return []


def get_ignore_contains(db_type):
    """
    Restituisce le stringhe che, se contenute nel nome di una tabella, fanno ignorare la tabella.

    Args:
        db_type (str): Tipo di database

    Returns:
        list: Lista di stringhe da cercare nel nome tabella
    """
    if db_type == "postgresql":
        return [
            "config",
            "settings",
            "report",
            "wizard",
        ]
    else:
        return [
            "FERMIPRODUZIONE"
        ]


def get_keywords_of_interest(db_type):
    """
    Restituisce le parole chiave di interesse per il tipo di database.

    Args:
        db_type (str): Tipo di database

    Returns:
        list: Lista di parole chiave
    """
    if db_type == "postgresql":
        return [
            "partner", "product", "invoice", "sale", "purchase",
            "stock", "account", "country", "company",
            "mrp", "maintenance", "fleet", "hr", "itinerary"
        ]
    else:
        return [
            "produzione", "clienti", "articoli", "clientiarticoli", "allarmi"
        ]


def should_ignore_table(table_name, ignore_prefixes, ignore_contains):
    """
    Determina se una tabella dovrebbe essere ignorata.

    Args:
        table_name (str): Nome della tabella
        ignore_prefixes (list): Lista di prefissi da ignorare
        ignore_contains (list): Lista di stringhe che, se presenti, fanno ignorare la tabella

    Returns:
        bool: True se la tabella dovrebbe essere ignorata
    """
    should_ignore_p = any(table_name.startswith(prefix) for prefix in ignore_prefixes)
    should_ignore_c = any(prefix in table_name for prefix in ignore_contains)
    should_ignore_s = table_name.endswith("_rel")

    return should_ignore_p or should_ignore_c or should_ignore_s


def get_cached_db_schema():
    """
    Recupera la struttura del database dalla cache locale.

    Returns:
        dict: Schema del database dalla cache o None se non disponibile
    """
    if not os.path.exists(DB_SCHEMA_CACHE_PATH):
        logger.warning("⚠️ Nessuna cache trovata per lo schema del database")
        return {}

    with open(DB_SCHEMA_CACHE_PATH, "r") as f:
        return json.load(f)


def get_db_structure_hash():
    """
    Genera un hash SHA256 basato sulla cache della struttura del database.

    Returns:
        str: Hash SHA256 della struttura del DB o None se non disponibile
    """
    db_schema = get_cached_db_schema()
    if not db_schema:
        return None  # Nessuna cache disponibile

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
