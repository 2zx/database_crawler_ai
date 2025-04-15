"""
Modulo per la generazione e l'esecuzione di query SQL basate su linguaggio naturale.
Gestisce il flusso completo dalla domanda alla generazione della query,
alla sua esecuzione e l'analisi dei risultati.
"""
import os
import math
import time
import pandas as pd  # type: ignore
import matplotlib.pyplot as plt  # type: ignore
from sqlalchemy.sql import text   # type: ignore
from sqlalchemy.exc import SQLAlchemyError  # type: ignore
from backend.utils.logging import get_logger
from backend.utils.helpers import clean_query, clean_generated_code
from backend.core.llm_manager import get_llm_instance
from backend.config import CHARTS_DIR, MAX_QUERY_ATTEMPTS, MAX_TOKEN_DEFAULT

# Configura il logging
logger = get_logger(__name__)


def generate_sql_query(domanda, db_schema, llm_config, db_type, hints_category=None):
    """
    Genera una query SQL basata sulla domanda dell'utente e sulla struttura del database.

    Args:
        domanda (str): La domanda dell'utente in linguaggio naturale
        db_schema (dict): Dizionario contenente la struttura del database
        llm_config (dict): Configurazione del LLM (provider, api_key, ecc.)
        db_type (str): Tipo di database ("postgresql" o "sqlserver")
        hints_category (str, optional): Categoria di hint da utilizzare

    Returns:
        str: Una query SQL generata dall'AI
    """
    # Otteniamo gli hint attivi formattati per il prompt
    formatted_hints = ""
    if hints_category:
        from backend.db.hint_store import HintStore
        hint_store = HintStore()
        formatted_hints = hint_store.format_hints_for_prompt(hints_category)

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
    La query NON DEVE restituire più di 100 righe di dati: crea opportuni raggruppameti o filtri senza inficiare i dati stessi.
    NON restituire ID o identificatori univoci, cerca sempre le relazioni tra le tabelle per restituire dati e nomi utili
    ad un utente umano.
    {syntax_notes}

    **Struttura del Database:**
    {db_schema}

    {hints_section}

    **Domanda dell'utente:**
    "{domanda}"

    Verifica che la query sia sintatticamente corretta per {db_type_desc}.
    Non generare mai valori inventati.
    Se la domanda include richieste relative a dati non presenti sul database della lavanderia
    restituisci una query che ritorni il messaggio "dato non disponibile nel database della lavanderia"
    """

    provider = llm_config.get("provider", "openai")

    try:
        # Ottieni l'istanza LLM appropriata
        llm_instance = get_llm_instance(provider, llm_config)

        logger.info(f"🔍 Generazione della query SQL con {provider}")

        # Genera la query SQL
        sql_query = llm_instance.generate_query(prompt_sql)

        return sql_query

    except Exception as e:
        logger.error(f"❌ Errore durante la generazione della query SQL con {provider}: {e}")
        return None


def try_query_execution(db_type, query, connection):
    """
    Prova a eseguire una query in modalità preview (senza recuperare risultati).

    Args:
        db_type (str): Tipo di database
        query (str): Query SQL da testare
        connection: Connessione al database

    Raises:
        Exception: Se la query non è valida
    """
    if db_type == 'postgresql':
        connection.execute(text("EXPLAIN " + query))
    elif db_type == 'sqlserver':
        connection.execute(text("SET SHOWPLAN_ALL ON;"))
        connection.execute(text(query))
        connection.execute(text("SET SHOWPLAN_ALL OFF;"))
    else:
        raise ValueError(f"Tipo di database non supportato: {db_type}")


def generate_query_with_retry(
        domanda, db_schema, llm_config, use_cache, engine, query_cache_manager,
        hints_category=None, max_attempts=MAX_QUERY_ATTEMPTS, progress_callback=None):
    """
    Esegue una query SQL generata dall'AI con sistema di retry in caso di errori sintattici.

    Args:
        domanda (str): La domanda dell'utente in linguaggio naturale
        db_schema (dict): Struttura del database
        llm_config (dict): Configurazione del modello LLM
        use_cache (bool): Se True, controlla prima la cache
        engine: Connessione al database SQLAlchemy
        query_cache_manager: Gestore della cache delle query
        hints_category (str, optional): Categoria di hint da utilizzare
        max_attempts (int): Numero massimo di tentativi
        progress_callback (func): Funzione per aggiornare il progresso

    Returns:
        tuple: (query_sql, cache_used, tentativi_effettuati)
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

    # Ottieni l'hash della struttura del database corrente
    from backend.core.db_schema import get_db_structure_hash
    current_db_hash = get_db_structure_hash()

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

        cached_query = query_cache_manager.get_cached_query(domanda, db_hash=current_db_hash)
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
                query_cache_manager.delete_cached_query(domanda)

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

        logger.info(f"✅ Query ripulita: {query_sql}")

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

                logger.info(f"✅ Anteprima query (explain) eseguita con successo al tentativo {attempts}/{max_attempts}")
                logger.info(f"⏱️ Tempo di esecuzione: {execution_time:.2f} secondi")

                # Notifica successo
                update_progress(
                    "success",
                    f"Query validata con successo in {execution_time:.2f} secondi!",
                    "execute_sql_success",
                    progress_base + progress_per_attempt
                )

                # Se non è dalla cache, salviamo la query
                if not cache_used:
                    update_progress(
                        "saving_to_cache",
                        "Salvataggio query nella cache...",
                        "save_to_cache",
                        progress_base + progress_per_attempt + 5
                    )
                    # Salva la query nella cache
                    query_cache_manager.save_query_to_cache(domanda, query_sql, current_db_hash)

                # La query è stata eseguita con successo
                return query_sql, False, attempts

        except SQLAlchemyError as e:
            # Salva l'errore per il prossimo tentativo
            error_message = str(e)
            error_history.append(error_message)

            logger.warning(f"❌ Tentativo {attempts}/{max_attempts} fallito con errore: {error_message}")

            # Notifica errore
            update_progress(
                "retry",
                f"Errore SQL: {error_message}",
                "execute_sql_failed",
                current_progress + progress_per_attempt / 2
            )

            # Se questo era l'ultimo tentativo, restituisci None
            if attempts >= max_attempts:
                logger.warning(f"⚠️ Numero massimo di tentativi ({max_attempts}) raggiunto. Impossibile eseguire la query.")

                query_cache_manager.delete_cached_query(domanda)  # Elimina la query dalla cache

                update_progress(
                    "failed",
                    f"Fallimento dopo {max_attempts} tentativi",
                    "max_attempts_reached",
                    70
                )
                return query_sql, False, attempts

    # Non dovremmo mai arrivare qui, ma per sicurezza
    return query_sql, False, attempts


def process_query_results(engine, sql_query, domanda, llm_config, progress_callback=None):
    """
    Esegue la query SQL generata dall'AI, analizza i dati e restituisce una risposta leggibile.

    Args:
        engine: Connessione SQLAlchemy al database
        sql_query (str): Query SQL da eseguire
        domanda (str): Domanda originale dell'utente
        llm_config (dict): Configurazione del modello LLM
        progress_callback (func, optional): Callback per aggiornare il progresso

    Returns:
        dict: Risultato dell'analisi con dati, descrizione e grafici
    """
    try:
        if progress_callback:
            progress_callback.update({
                "status": "processing",
                "progress": 70,
                "message": "Esecuzione query...",
                "step": "execute_sql"
            })

        # Connessione corretta con SQLAlchemy
        with engine.connect() as connection:
            df = pd.read_sql(text(sql_query), connection)

        if df.empty:
            return {
                "descrizione": "⚠️ Nessun dato trovato.", "dati": [], "grafici": []
            }

        # Convertiamo le colonne datetime in UTC
        for col in df.select_dtypes(include=["datetime64", "object"]).columns:
            try:
                df[col] = pd.to_datetime(df[col], utc=True)
            except Exception:
                pass  # Se fallisce, lasciamo la colonna invariata

        # Selezioniamo il provider LLM appropriato
        provider = llm_config.get("provider", "openai")
        llm_instance = get_llm_instance(provider, llm_config)

        # Prepariamo un prompt per l'analisi dei dati
        data_sample = df.head(100).to_string()
        analysis_prompt = f"""
        **Domanda dell'utente**
        "{domanda}"

        **Dati recuperati dal database (primi 100 record):**
        {data_sample}

        **Statistiche dei dati:**
        {df.describe().to_string()}

        Sulla base della domanda, dei dati forniti e delle istruzioni sull'interpretazione dei dati,
        descrivi in modo chiaro e utile i risultati.
        Fornisci un'analisi che aiuti l'utente a comprendere i dati.
        Rispondi nella lingua dell'utente senza proporre grafici, solo testo.
        Fai riferimento alle istruzioni sull'interpretazione dei dati quando opportuno.
        Se l'utente chiede dati non presenti nel database della lavanderia fai una ricerca tra i dati che conosci
        a livello globale evidenziando all'utente che stai usando dati pubblici.
        """

        if progress_callback:
            progress_callback.update({
                "status": "processing",
                "progress": 80,
                "message": "Analisi risultati...",
                "step": "process_results"
            })

        risposta = llm_instance.generate_analysis(analysis_prompt)

        if progress_callback:
            progress_callback.update({
                "status": "processing",
                "progress": 90,
                "message": "Creazione visualizzazioni...",
                "step": "generate_charts"
            })

        plot_code = None
        if "dato non disponibile" not in data_sample:
            # Generiamo il codice per il grafico
            plot_code = generate_plot_code(df, llm_config)

        path_grafico = ""
        if plot_code:
            path_grafico = execute_generated_plot_code(plot_code)

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

    Args:
        df (pandas.DataFrame): DataFrame con i dati
        llm_config (dict): Configurazione del modello LLM

    Returns:
        str: Codice Python per la generazione del grafico
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
        plot_code = clean_generated_code(plot_code)  # Rimuoviamo ```python e ```

        # Salviamo il codice in un file Python per debugging
        with open(f"{CHARTS_DIR}/generated_plot.py", "w") as f:
            f.write(plot_code)

        return plot_code
    except Exception as e:
        logger.error(f"❌ Errore nella generazione del codice del grafico: {str(e)}")
        return None


def execute_generated_plot_code(plot_code):
    """
    Esegue il codice Matplotlib generato dall'AI in un ambiente sicuro.

    Args:
        plot_code (str): Codice Python da eseguire

    Returns:
        str: Percorso del file salvato o messaggio di errore
    """
    try:
        logger.info("📊 Esecuzione del codice generato per il grafico")

        # Assicurati che la directory esista
        os.makedirs(CHARTS_DIR, exist_ok=True)

        # Esegui il codice in un ambiente isolato
        local_vars = {"plt": plt, "pd": pd}
        exec(plot_code, {"plt": plt, "pd": pd}, local_vars)

        logger.info("📊 Esecuzione OK")
        return os.path.join(CHARTS_DIR, "generated_plot.png")
    except Exception as e:
        logger.error(f"Errore nell'esecuzione del codice generato: {e}")
        return f"Errore nell'esecuzione del codice generato: {e}"


def generate_related_questions(results, domanda, llm_config, max_questions=3):
    """
    Genera domande correlate basate sui risultati dell'analisi precedente.

    Args:
        results (dict): I risultati dell'analisi precedente
        domanda (str): La domanda originale dell'utente
        llm_config (dict): Configurazione del LLM
        max_questions (int): Numero massimo di domande da generare

    Returns:
        list: Lista di domande correlate
    """
    try:
        # Selezioniamo il provider LLM appropriato
        provider = llm_config.get("provider", "openai")
        llm_instance = get_llm_instance(provider, llm_config)

        # Prepariamo il contesto dalla domanda originale e dai risultati
        context = f"""
        Domanda originale: "{domanda}"

        Descrizione dei risultati: "{results['descrizione']}"

        Dati: {results['dati'][:5] if results['dati'] else 'Nessun dato'}
        """

        # Generiamo le domande correlate
        related_questions = llm_instance.generate_related_questions(
            context=context,
            results=results,
            max_questions=max_questions
        )

        return related_questions

    except Exception as e:
        logger.error(f"❌ Errore nella generazione delle domande correlate: {str(e)}")
        return []
