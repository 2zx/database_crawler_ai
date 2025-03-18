import base64
import io
import pandas as pd
import matplotlib.pyplot as plt
import os
from sqlalchemy.sql import text
from openai import OpenAI
from pandasai import SmartDataframe
from pandasai.llm.openai import OpenAI as OpenAILLM
from query_cache import get_cached_query, save_query_to_cache
import logging

# Configura il logging per vedere gli errori nel container
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AI_MODEL = "gpt-4o-mini"
EXPORT_PATH = "exports/charts/"
os.makedirs(EXPORT_PATH, exist_ok=True)

OPENAI_CLIENT = None


def encode_figure_to_base64(fig):
    """
    Converte un oggetto Matplotlib Figure in una stringa Base64 per inviarlo al frontend.
    """
    img_bytes = io.BytesIO()
    fig.savefig(img_bytes, format="png", bbox_inches="tight")
    img_bytes.seek(0)
    return base64.b64encode(img_bytes.read()).decode("utf-8")


def generate_sql_query(domanda, db_schema, openai_api_key, use_cache=True):
    """
    Genera una query SQL basata sulla domanda dell'utente e sulla struttura del database.

    :param domanda: La domanda dell'utente in linguaggio naturale
    :param db_schema: Dizionario contenente la struttura del database (tabelle, colonne, chiavi esterne)
    :param openai_api_key: La chiave API di OpenAI per la generazione della query
    :return: Una query SQL generata dall'AI
    """

    # ✅ 1️⃣ Controlliamo la cache intelligente
    if use_cache:
        cached_query = get_cached_query(domanda)
        if cached_query:
            logger.info(f"✅ Cache hit! Usata query SQL già salvata per '{domanda}'")
            return cached_query, True  # ✅ Usiamo la query salvata

    prompt_sql = f"""
    Sei un esperto di database SQL. Ti verrà fornita la struttura di un database PostgreSQL,
    e la domanda dell'utente. Devi restituire **solo** la query SQL necessaria per ottenere la risposta.

    **Struttura del Database:**
    {db_schema}

    **Domanda dell'utente:**
    "{domanda}"

    Genera **solo** la query SQL senza alcuna spiegazione o testo aggiuntivo.
    Verifica che la query sia sintatticamente corretta e coerente con la struttura del database e con la domanda dell'utente.
    Ricontrolla più volte in base allo schema DB per assicurarti che restituisca i risultati attesi.
    Non generare mai valori inventati.
    """

    get_openai_client(openai_api_key)

    try:
        response = OPENAI_CLIENT.chat.completions.create(
            model=AI_MODEL,  # ✅ Usiamo gpt-4o-mini per generare query SQL
            messages=[
                {"role": "system", "content": "Sei un assistente SQL esperto."},
                {"role": "user", "content": prompt_sql}
            ]
        )

        sql_query = response.choices[0].message.content.strip()

        # ✅ 3️⃣ Salviamo la query nella cache con il suo embedding
        save_query_to_cache(domanda, sql_query)

        return sql_query, False

    except Exception as e:
        print(f"❌ Errore durante la generazione della query SQL: {e}")
        return None, None


def process_query_results(engine, sql_query, domanda, openai_api_key):
    """
    Esegue la query SQL generata dall'AI, analizza i dati e restituisce una risposta leggibile.
    """
    try:
        # rimuovo prefisso SQL se presente
        if "```" in sql_query:
            sql_query = sql_query.split("```")[1].strip()
        if sql_query.lower().startswith("sql"):
            sql_query = sql_query[3:].strip()

        # Verifica se la query è valida
        if not sql_query.lower().startswith("select"):
            logger.error(f"❌ Query non valida generata: {sql_query}")
            raise Exception("L'AI ha generato una query non valida.")

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

        # ✅ Configurazione OpenAI per PandasAI
        llm = OpenAILLM(api_token=openai_api_key, model=AI_MODEL)
        sdf = SmartDataframe(df, config={
            "llm": llm,
            "save_charts": False,
            "custom_whitelisted_dependencies": ["pandas", "matplotlib", "numpy", "seaborn", "plotly"]
        })

        # ✅ Chiediamo all'AI di spiegare i dati senza grafici
        risposta = sdf.chat(f"""
            **Domanda dell'utente**
            "{domanda}"

            Sulla base della domanda descrivi i dati forniti in modo chiaro e utile
            nella lingua dell'utente senza grafici, solo testo.""")

        plot_code = generate_plot_code_with_gpt(df, openai_api_key)  # ✅ Generiamo il codice per il grafico

        if plot_code:
            path_grafico = execute_generated_plot_code(plot_code)  # ✅ Eseguiamo il codice per generare il grafico

        return {
            "descrizione": risposta,
            "dati": df.to_dict(orient="records"),
            "grafici": path_grafico if "generated_plot" in path_grafico else None  # ✅ Restituiamo i grafici generati dall'AI
        }

    except Exception as e:

        return {
            "errore": f"❌ Errore nell'elaborazione dei dati: {str(e)}",
            "descrizione": "❌ Errore nell'analisi.",
            "dati": [],
            "grafici": []
        }


def generate_plot_code_with_gpt(df, openai_api_key):
    """
    Chiede a OpenAI di generare codice Matplotlib basato sui dati.
    """
    prompt = f"""
    Genera un grafico Matplotlib per visualizzare i seguenti dati:
    {df.head().to_string()}

    Il codice deve:
    - Usare plt.plot(), plt.bar() o plt.scatter() in base ai dati.
    - Aggiungere titolo, assi e griglia.
    - Salvare l'immagine in '{EXPORT_PATH}/generated_plot.png'.
    - Non mostrare il grafico (plt.show()).

    Ritorna SOLO il codice Python, senza commenti o altro.
    """

    get_openai_client(openai_api_key)

    response = OPENAI_CLIENT.chat.completions.create(
        model=AI_MODEL,
        messages=[{"role": "system", "content": "Sei un esperto di analisi dati."},
                  {"role": "user", "content": prompt}]
    )

    plot_code = response.choices[0].message.content.strip()
    plot_code = clean_generated_code(plot_code)  # ✅ Rimuoviamo ```python e ```

    # ✅ Salviamo il codice in un file Python per debugging
    with open(f"{EXPORT_PATH}/generated_plot.py", "w") as f:
        f.write(plot_code)

    return plot_code


def get_openai_client(openai_api_key):
    global OPENAI_CLIENT
    if not OPENAI_CLIENT:
        OPENAI_CLIENT = OpenAI(api_key=openai_api_key)


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
    Esegue il codice Matplotlib generato da OpenAI in un ambiente sicuro.
    """
    try:
        logger.info("📊 Esecuzione del codice generato per il grafico")
        exec(plot_code, {"plt": plt, "pd": pd})
        logger.info("📊 Esecuzione OK")
        return f"{EXPORT_PATH}/generated_plot.png"
    except Exception as e:
        logger.error(f"Errore nell'esecuzione del codice generato: {e}")
        return f"Errore nell'esecuzione del codice generato: {e}"
