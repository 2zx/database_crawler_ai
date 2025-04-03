import base64
import io
import math
import pandas as pd  # type: ignore
import matplotlib.pyplot as plt  # type: ignore
import os
import time
from sqlalchemy.sql import text  # type: ignore
from sqlalchemy.exc import SQLAlchemyError  # type: ignore
from query_cache import get_cached_query, save_query_to_cache, delete_cached_query
from hint_manager import format_hints_for_prompt
import logging
from llm_manager import get_llm_instance
from config import CHARTS_DIR

# Configura il logging per vedere gli errori nel container
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ora supportiamo diversi LLM
LLM_INSTANCE = None
DEFAULT_MAX_TOKENS = 1000


def encode_figure_to_base64(fig):
    """
    Converte un oggetto Matplotlib Figure in una stringa Base64 per inviarlo al frontend.
    """
    img_bytes = io.BytesIO()
    fig.savefig(img_bytes, format="png", bbox_inches="tight")
    img_bytes.seek(0)
    return base64.b64encode(img_bytes.read()).decode("utf-8")


def generate_sql_query(domanda, db_schema, llm_config, db_type, hints_category):
    """
    Genera una query SQL basata sulla domanda dell'utente e sulla struttura del database.

    :param domanda: La domanda dell'utente in linguaggio naturale
    :param db_schema: Dizionario contenente la struttura del database (tabelle, colonne, chiavi esterne)
    :param llm_config: Configurazione del LLM (provider, api_key, ecc.)
    :param db_type: Tipo di database ("postgresql" o "sqlserver")
    :return: Una query SQL generata dall'AI
    """

    # Otteniamo gli hint attivi formattati per il prompt
    formatted_hints = format_hints_for_prompt(hints_category)
    hints_section = f"\n\n{formatted_hints}\n" if formatted_hints else ""

    # Adatta il prompt in base al tipo di database
    db_type_desc = "PostgreSQL" if db_type == "postgresql" else "Microsoft SQL Server"

    # Aggiungi eventuali differenze sintattiche specifiche per SQL Server
    syntax_notes = ""
    if db_type == "sqlserver":
        syntax_notes = """
        Note specifiche per SQL Server:
        - Usa TOP invece di LIMIT per limitare i risultati
        - Usa GETDATE() invece di NOW() per la data corrente
        - Usa DATEADD() e DATEDIFF() per le operazioni sulle date
        - Usa CONVERT() invece di CAST() per le conversioni di tipo
        - Le stringhe sono racchiuse tra apici singoli
        - Per limitare e ordinare contemporaneamente, usa ORDER BY prima di TOP
        """

    prompt_sql = f"""
    Sei un esperto di database SQL. Ti verrà fornita la struttura di un database {db_type_desc},
    comprensivo di tabelle, colonne, chiavi primarie e commenti.
    Riceverai una domanda posta da un utente in linguaggio naturale.
    Dovrai generare una query SQL che risponda alla domanda dell'utente restituendo **solo**
    la query SQL necessaria per ottenere la risposta senza alcuna spiegazione o testo aggiuntivo.
    {syntax_notes}

    **Struttura del Database:**
    {db_schema}{hints_section}

    **Domanda dell'utente:**
    "{domanda}"

    Verifica che la query sia sintatticamente corretta per {db_type_desc}.
    Non generare mai valori inventati.
    """

    provider = llm_config.get("provider", "openai")

    try:
        # Ottieni l'istanza LLM appropriata
        llm_instance = get_llm_instance(provider, llm_config)

        logger.info(f"🔍 Generazione della query SQL con prompt: {prompt_sql}")

        # Genera la query SQL
        sql_query = llm_instance.generate_query(prompt_sql)

        return sql_query

    except Exception as e:
        logger.error(f"❌ Errore durante la generazione della query SQL con {provider}: {e}")
        return None


def generate_query_with_retry(
        domanda, db_schema, llm_config, use_cache, engine, hints_category,
        max_attempts=3, progress_callback=None):
    """
    Esegue una query SQL generata dall'AI con sistema di retry in caso di errori sintattici.

    Args:
        domanda (str): La domanda dell'utente in linguaggio naturale
        db_schema (dict): Struttura del database
        llm_config (dict): Configurazione del modello LLM
        use_cache (bool): Se True, controlla prima la cache
        engine: Connessione al database SQLAlchemy
        max_attempts (int): Numero massimo di tentativi
        progress_callback (func): Funzione per aggiornare il progresso

    Returns:
        tuple: (query_sql, cache_used, tentativi_effettuati)
            - query_sql: L'ultima query SQL tentata
            - cache_used: Indica se la query è stata recuperata dalla cache
            - tentativi_effettuati: Numero di tentativi effettuati
    """

    # Determina il tipo di database dall'engine
    db_type = engine.dialect.name
    # Converti il nome del dialetto in 'postgresql' o 'sqlserver'
    if db_type.startswith('mysql'):
        db_type = 'mysql'
    elif db_type.startswith('mssql') or db_type.startswith('pyodbc'):
        db_type = 'sqlserver'
    else:
        db_type = 'postgresql'  # Default

    attempts = 0
    error_history = []
    query_sql = None
    cache_used = False

    # Funzione per aggiornare il progresso
    def update_progress(status, message, step, progress):
        if progress_callback:
            progress_callback(status, message, step, progress)

    # Prima controlliamo la cache se use_cache è True
    if use_cache:
        update_progress(
            "checking_cache",
            "Ricerca nella cache query simili...",
            "check_cache",
            30
        )

        cached_query = get_cached_query(domanda)
        if cached_query:
            update_progress(
                "cache_hit",
                "Trovata query simile in cache!",
                "cache_hit",
                40
            )

            # Verifica che la query sia valida provando a eseguirla
            try:
                with engine.connect() as connection:
                    # Utilizziamo EXPLAIN per verificare la validità della query senza eseguirla completamente
                    try_query_execution(db_type, cached_query, connection)

                update_progress(
                    "cache_valid",
                    "Query dalla cache verificata e valida",
                    "cache_valid",
                    45
                )

                logger.info(f"✅ Cache hit! Usata query SQL già salvata per '{domanda}'")
                return cached_query, True, 0
            except SQLAlchemyError as e:
                update_progress(
                    "cache_invalid",
                    f"Query dalla cache non valida: {str(e)}",
                    "cache_invalid",
                    35
                )

                # La query dalla cache non è valida, proseguiamo con la generazione
                logger.info(f"⚠️ Query dalla cache non valida, procedo con generazione: {str(e)}")
                # Elimina la query non valida dalla cache
                delete_cached_query(domanda)

    # Base progresso: ogni tentativo vale circa il 10% del totale (40-70%)
    progress_base = 40
    progress_per_attempt = 10

    while attempts < max_attempts:
        attempts += 1
        current_progress = progress_base + (attempts - 1) * progress_per_attempt

        # Notifica l'inizio di un nuovo tentativo
        update_progress(
            "generating",
            f"Tentativo {attempts}/{max_attempts} di generare SQL...",
            "generate_sql",
            current_progress
        )

        # Genera la query, includendo eventuali errori precedenti nel prompt
        error_context = ""
        if error_history:
            error_context = "\n\nLa query precedente ha generato il seguente errore: " + \
                f"\n{error_history[-1]}\n" + \
                "Correggi l'errore sintattico e genera una query SQL valida."

        # Combina domanda originale ed errori
        query_prompt = domanda + error_context

        # Genera la query SQL
        query_sql = generate_sql_query(query_prompt, db_schema, llm_config, db_type, hints_category)

        # Se non è stata generata una query valida, continua
        if not query_sql:
            error_msg = "La generazione della query è fallita."
            error_history.append(error_msg)
            update_progress(
                "error",
                f"Errore: {error_msg}",
                "generate_sql_failed",
                current_progress
            )
            continue

        # Pulisci il formato della query se necessario
        query_sql = clean_query(query_sql)

        print(f"✅ Query ripulita: {query_sql}")

        # Notifica che stiamo per eseguire la query
        update_progress(
            "executing",
            f"Esecuzione query (tentativo {attempts}/{max_attempts})...",
            "execute_sql",
            current_progress + progress_per_attempt / 2
        )

        try:
            # Prova a eseguire la query
            with engine.connect() as connection:
                start_time = time.time()
                try_query_execution(db_type, query_sql, connection)
                execution_time = time.time() - start_time

                print(f"✅ Anteprima query (explain) eseguita con successo al tentativo {attempts}/{max_attempts}")
                print(f"⏱️ Tempo di esecuzione: {execution_time:.2f} secondi")

                # Notifica successo
                update_progress(
                    "success",
                    f"Query validata con successo in {execution_time:.2f} secondi!",
                    "execute_sql_success",
                    progress_base + progress_per_attempt
                )

                # Se non è dalla cache, salviamo la query
                if use_cache and not cache_used:
                    update_progress(
                        "saving_to_cache",
                        "Salvataggio query nella cache...",
                        "save_to_cache",
                        progress_base + progress_per_attempt + 5
                    )

                    # Salviamo nella cache solo se use_cache è True
                    save_query_to_cache(domanda, query_sql)

                # La query è stata eseguita con successo
                return query_sql, False, attempts

        except SQLAlchemyError as e:
            # Salva l'errore per il prossimo tentativo
            error_message = str(e)
            error_history.append(error_message)

            print(f"❌ Tentativo {attempts}/{max_attempts} fallito con errore: {error_message}")

            # Notifica errore
            update_progress(
                "retry",
                f"Errore SQL: {error_message}",
                "execute_sql_failed",
                current_progress + progress_per_attempt / 2
            )

            # Se questo era l'ultimo tentativo, restituisci None
            if attempts >= max_attempts:
                print(f"⚠️ Numero massimo di tentativi ({max_attempts}) raggiunto. Impossibile eseguire la query.")

                delete_cached_query(domanda)  # Elimina la query dalla cache

                update_progress(
                    "failed",
                    f"Fallimento dopo {max_attempts} tentativi",
                    "max_attempts_reached",
                    70
                )
                return query_sql, False, attempts

    # Non dovremmo mai arrivare qui, ma per sicurezza
    return query_sql, False, attempts


def try_query_execution(db_type, cached_query, connection):
    if db_type == 'postgresql':
        connection.execute(text("explain " + cached_query))
    elif db_type == 'sqlserver':
        connection.execute(text("SET SHOWPLAN_ALL ON;"))
        connection.execute(text(cached_query))
        connection.execute(text("SET SHOWPLAN_ALL OFF;"))
    else:
        raise ValueError(f"Tipo di database non supportato: {db_type}")


def clean_query(query_sql):
    """
    Pulisce la query SQL rimuovendo eventuali markdown o formattazioni aggiuntive.

    Args:
        query_sql (str): La query SQL potenzialmente con formattazione

    Returns:
        str: La query SQL pulita
    """
    if not query_sql:
        return ""

    # Rimuovi i blocchi di codice markdown
    if "```" in query_sql:
        # Estrai la query dal blocco di codice
        lines = query_sql.split("\n")
        cleaned_lines = []
        inside_code_block = False

        for line in lines:
            if line.strip().startswith("```"):
                inside_code_block = not inside_code_block
                continue

            if inside_code_block or "```" not in query_sql:
                cleaned_lines.append(line)

        query_sql = "\n".join(cleaned_lines)

    # Rimuovi eventuali prefissi "sql" all'inizio della query
    query_sql = query_sql.strip()
    if query_sql.lower().startswith("sql"):
        query_sql = query_sql[3:].strip()

    return query_sql


def process_query_results(engine, sql_query, domanda, llm_config):
    """
    Esegue la query SQL generata dall'AI, analizza i dati e restituisce una risposta leggibile.
    """
    try:

        # ✅ Connessione corretta con SQLAlchemy 2.0
        with engine.connect() as connection:
            df = pd.read_sql(text(sql_query), connection)  # ✅ Usa text() e connection

        if df.empty:
            return {
                "descrizione": "⚠️ Nessun dato trovato.", "dati": [], "grafici": []
            }  # ✅ Risposta predefinita se non ci sono dati

        # ✅ Convertiamo le colonne datetime in UTC
        for col in df.select_dtypes(include=["datetime64", "object"]).columns:
            try:
                df[col] = pd.to_datetime(df[col], utc=True)
            except Exception:
                pass  # Se fallisce, lasciamo la colonna invariata

        # Selezioniamo il provider LLM appropriato
        provider = llm_config.get("provider", "openai")
        llm_instance = get_llm_instance(provider, llm_config)

        # Prepariamo un prompt per l'analisi dei dati
        data_sample = df.head(50).to_string()
        analysis_prompt = f"""
        **Domanda dell'utente**
        "{domanda}"

        **Dati recuperati dal database (primi 50 record):**
        {data_sample}

        **Statistiche dei dati:**
        {df.describe().to_string()}

        Sulla base della domanda, dei dati forniti e delle istruzioni sull'interpretazione dei dati,
        descrivi in modo chiaro e utile i risultati.
        Fornisci un'analisi che aiuti l'utente a comprendere i dati.
        Rispondi nella lingua dell'utente senza proporre grafici, solo testo.
        Fai riferimento alle istruzioni sull'interpretazione dei dati quando opportuno.
        """

        risposta = llm_instance.generate_analysis(analysis_prompt)

        # ✅ Generiamo il codice per il grafico
        plot_code = generate_plot_code(df, llm_config)

        path_grafico = ""
        if plot_code:
            path_grafico = execute_generated_plot_code(plot_code)  # ✅ Eseguiamo il codice per generare il grafico

        # Prima di restituire la risposta, sanitizza i valori float
        sanitized_data = []
        for record in df.to_dict(orient="records"):
            sanitized_record = {}
            for key, value in record.items():
                # Gestisci valori float anomali
                if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                    sanitized_record[key] = None
                else:
                    sanitized_record[key] = value
            sanitized_data.append(sanitized_record)

        return {
            "descrizione": risposta,
            "dati": sanitized_data,  # Usa i dati sanitizzati
            "grafici": path_grafico if "generated_plot" in path_grafico else None
        }

    except Exception as e:
        logger.error(f"❌ Errore nell'elaborazione dei dati: {str(e)}")
        return {
            "errore": f"❌ Errore nell'elaborazione dei dati: {str(e)}",
            "descrizione": "❌ Errore nell'analisi.",
            "dati": [],
            "grafici": []
        }


def generate_plot_code(df, llm_config):
    """
    Chiede all'AI di generare codice Matplotlib basato sui dati.
    """

    prompt = f"""
    Genera più grafici Matplotlib identificando multipli KPI per visualizzare i seguenti dati:
    {df.head().to_string()}

    Il codice deve:
    - Usare plt.plot(), plt.bar() o plt.scatter() in base ai dati.
    - Aggiungere titolo, assi e griglia per ogni grafico.
    - Salvare il tutto in una sola immagine in '{CHARTS_DIR}/generated_plot.png'.
    - Non mostrare i grafici (plt.show()).
    - Tenere in considerazione le istruzioni per l'interpretazione dei dati.

    Ritorna SOLO il codice Python, senza commenti o altro.
    """

    provider = llm_config.get("provider", "openai")

    try:
        # Ottieni l'istanza LLM appropriata
        llm_instance = get_llm_instance(provider, llm_config)

        # Genera il codice per il grafico
        plot_code = llm_instance.generate_query(prompt)
        plot_code = clean_generated_code(plot_code)  # ✅ Rimuoviamo ```python e ```

        # ✅ Salviamo il codice in un file Python per debugging
        with open(f"{CHARTS_DIR}/generated_plot.py", "w") as f:
            f.write(plot_code)

        return plot_code
    except Exception as e:
        logger.error(f"❌ Errore nella generazione del codice del grafico: {str(e)}")
        return None


def clean_generated_code(code):
    """
    Rimuove le righe ` ```python ` e ` ``` ` dal codice generato.
    """
    lines = code.strip().split("\n")

    # ✅ Se il codice inizia con ```python, rimuoviamo la prima riga
    if lines[0].startswith("```"):
        lines = lines[1:]

    # ✅ Se il codice termina con ```, rimuoviamo l'ultima riga
    if lines[-1].startswith("```"):
        lines = lines[:-1]

    return "\n".join(lines)


def execute_generated_plot_code(plot_code):
    """
    Esegue il codice Matplotlib generato dall'AI in un ambiente sicuro.
    """
    try:
        logger.info("📊 Esecuzione del codice generato per il grafico")
        exec(plot_code, {"plt": plt, "pd": pd})
        logger.info("📊 Esecuzione OK")
        return os.path.join(CHARTS_DIR, "generated_plot.png")
    except Exception as e:
        logger.error(f"Errore nell'esecuzione del codice generato: {e}")
        return f"Errore nell'esecuzione del codice generato: {e}"
