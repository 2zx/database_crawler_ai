import base64
import io
import math
import pandas as pd  # type: ignore
import matplotlib.pyplot as plt  # type: ignore
import os
import time
from sqlalchemy.sql import text  # type: ignore
from sqlalchemy.exc import SQLAlchemyError  # type: ignore
from pandasai import SmartDataframe  # type: ignore
from pandasai.llm.openai import OpenAI as OpenAILLM  # type: ignore
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


def generate_sql_query(domanda, db_schema, llm_config, use_cache=True):
    """
    Genera una query SQL basata sulla domanda dell'utente e sulla struttura del database.

    :param domanda: La domanda dell'utente in linguaggio naturale
    :param db_schema: Dizionario contenente la struttura del database (tabelle, colonne, chiavi esterne)
    :param llm_config: Configurazione del LLM (provider, api_key, ecc.)
    :param use_cache: Se True, controlla prima la cache
    :return: Una query SQL generata dall'AI
    """

    # ✅ 1️⃣ Controlliamo la cache intelligente
    if use_cache:
        cached_query = get_cached_query(domanda)
        if cached_query:
            logger.info(f"✅ Cache hit! Usata query SQL già salvata per '{domanda}'")
            return cached_query, True  # ✅ Usiamo la query salvata

    # Otteniamo gli hint attivi formattati per il prompt
    formatted_hints = format_hints_for_prompt()
    hints_section = f"\n\n{formatted_hints}\n" if formatted_hints else ""

    prompt_sql = f"""
    Sei un esperto di database SQL. Ti verrà fornita la struttura di un database PostgreSQL,
    comprensivo di tabelle, colonne, chiavi primarie e straniere, indici e commenti.
    I commenti sono utili per capire il senso della colonna e il tipo di dati che contiene e come il devi interpretare.
    Riceverai una domanda posta da un utente in linguaggio naturale.
    Dovrai generare una query SQL che risponda alla domanda dell'utente.
    Devi restituire **solo** la query SQL necessaria per ottenere la risposta.

    **Struttura del Database:**
    {db_schema}{hints_section}

    **Domanda dell'utente:**
    "{domanda}"

    Genera **solo** la query SQL senza alcuna spiegazione o testo aggiuntivo.
    Verifica che la query sia sintatticamente corretta e coerente con la struttura del database e con la domanda dell'utente.
    Ricontrolla più volte in base allo schema DB per assicurarti che restituisca i risultati attesi.
    Non generare mai valori inventati.
    Assicurati di seguire le istruzioni sull'interpretazione dei dati fornite.
    """

    provider = llm_config.get("provider", "openai")

    try:
        # Ottieni l'istanza LLM appropriata
        llm_instance = get_llm_instance(provider, llm_config)

        # Genera la query SQL
        sql_query = llm_instance.generate_query(prompt_sql)

        # ✅ 3️⃣ Salviamo la query nella cache con il suo embedding
        # Salviamo nella cache solo se use_cache è True
        if use_cache:
            save_query_to_cache(domanda, sql_query)

        return sql_query, False

    except Exception as e:
        logger.error(f"❌ Errore durante la generazione della query SQL con {provider}: {e}")
        return None, None


def generate_query_with_retry(domanda, db_schema, llm_config, use_cache, engine, max_attempts=3):
    """
    Esegue una query SQL generata dall'AI con sistema di retry in caso di errori sintattici.

    Args:
        domanda (str): La domanda dell'utente in linguaggio naturale
        db_schema (dict): Struttura del database
        llm_config (dict): Configurazione del modello LLM
        engine: Connessione al database SQLAlchemy
        max_attempts (int): Numero massimo di tentativi

    Returns:
        tuple: (risultato, query_sql, tentativi_effettuati)
            - risultato: DataFrame con i risultati o None in caso di fallimento
            - query_sql: L'ultima query SQL tentata
            - tentativi_effettuati: Numero di tentativi effettuati
    """

    attempts = 0
    error_history = []
    query_sql = None

    while attempts < max_attempts:
        attempts += 1

        # Genera la query, includendo eventuali errori precedenti nel prompt
        error_context = ""
        if error_history:
            error_context = "\n\nLa query precedente ha generato il seguente errore: " + \
                f"\n{error_history[-1]}\n" + \
                "Correggi l'errore sintattico e genera una query SQL valida."

        # Combina domanda originale ed errori
        query_prompt = domanda + error_context

        # Genera la query SQL
        query_sql, cache_used = generate_sql_query(query_prompt, db_schema, llm_config, use_cache)

        # Se non è stata generata una query valida, continua
        if not query_sql:
            error_history.append("La generazione della query è fallita.")
            continue

        # Pulisci il formato della query se necessario
        query_sql = clean_query(query_sql)

        print(f"✅ Query ripulita: {query_sql}")

        try:
            # Prova a eseguire la query
            with engine.connect() as connection:
                start_time = time.time()
                result = pd.read_sql(text("explain " + query_sql), connection)
                execution_time = time.time() - start_time

                print(f"✅ Query eseguita con successo al tentativo {attempts}/{max_attempts}")
                print(f"⏱️ Tempo di esecuzione: {execution_time:.2f} secondi")

                # La query è stata eseguita con successo
                return query_sql, cache_used, attempts

        except SQLAlchemyError as e:
            # Salva l'errore per il prossimo tentativo
            error_message = str(e)
            error_history.append(error_message)

            print(f"❌ Tentativo {attempts}/{max_attempts} fallito con errore: {error_message}")

            # Se questo era l'ultimo tentativo, restituisci None
            if attempts >= max_attempts:
                print(f"⚠️ Numero massimo di tentativi ({max_attempts}) raggiunto. Impossibile eseguire la query.")

                delete_cached_query(domanda)  # Elimina la query dalla cache
                return query_sql, cache_used, attempts

    # Non dovremmo mai arrivare qui, ma per sicurezza
    return query_sql, cache_used, attempts


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

            if inside_code_block or not "```" in query_sql:
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

        # Otteniamo gli hint attivi formattati per il prompt
        formatted_hints = format_hints_for_prompt()
        hints_section = f"\n\n{formatted_hints}\n" if formatted_hints else ""

        # Selezioniamo il provider LLM appropriato
        provider = llm_config.get("provider", "openai")
        if provider == "openai":
            # ✅ Configurazione OpenAI per PandasAI
            llm = OpenAILLM(api_token=llm_config.get("api_key"), model=llm_config.get("model", "gpt-4o-mini"))
            sdf = SmartDataframe(df, config={
                "llm": llm,
                "save_charts": False,
                "custom_whitelisted_dependencies": ["pandas", "matplotlib", "numpy", "seaborn", "plotly"]
            })

            # ✅ Chiediamo all'AI di spiegare i dati senza grafici
            prompt_analysis = f"""
                **Domanda dell'utente**
                "{domanda}"

                {hints_section}

                Sulla base della domanda e delle istruzioni sull'interpretazione dei dati,
                descrivi i risultati in modo chiaro e utile nella lingua dell'utente senza grafici, solo testo.
                Fai riferimento alle istruzioni sull'interpretazione dei dati quando opportuno.
            """

            risposta = sdf.chat(prompt_analysis)
        else:
            # Per gli altri provider, possiamo usare direttamente le nostre classi LLM
            llm_instance = get_llm_instance(provider, llm_config)

            # Prepariamo un prompt per l'analisi dei dati con hint
            data_sample = df.head(10).to_string()
            analysis_prompt = f"""
            **Domanda dell'utente**
            "{domanda}"

            **Dati recuperati dal database (primi 10 record):**
            {data_sample}

            **Statistiche dei dati:**
            {df.describe().to_string()}
            {hints_section}

            Sulla base della domanda, dei dati forniti e delle istruzioni sull'interpretazione dei dati,
            descrivi in modo chiaro e utile i risultati.
            Fornisci un'analisi che aiuti l'utente a comprendere i dati.
            Rispondi nella lingua dell'utente senza proporre grafici, solo testo.
            Fai riferimento alle istruzioni sull'interpretazione dei dati quando opportuno.
            """

            risposta = llm_instance.generate_analysis(analysis_prompt)

        # ✅ Generiamo il codice per il grafico, includendo gli hint
        plot_code = generate_plot_code_with_gpt(df, llm_config)

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


def generate_plot_code_with_gpt(df, llm_config):
    """
    Chiede all'AI di generare codice Matplotlib basato sui dati.
    """
    # Otteniamo gli hint attivi formattati per il prompt
    formatted_hints = format_hints_for_prompt()
    hints_section = f"\n\n{formatted_hints}\n" if formatted_hints else ""

    prompt = f"""
    Genera un grafico Matplotlib per visualizzare i seguenti dati:
    {df.head().to_string()}

    {hints_section}

    Il codice deve:
    - Usare plt.plot(), plt.bar() o plt.scatter() in base ai dati.
    - Aggiungere titolo, assi e griglia.
    - Salvare l'immagine in '{CHARTS_DIR}/generated_plot.png'.
    - Non mostrare il grafico (plt.show()).
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
