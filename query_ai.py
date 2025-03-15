import base64
import io
import pandas as pd
import matplotlib.pyplot as plt
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
    """

    client = OpenAI(api_key=openai_api_key)  # ✅ Nuovo modo di inizializzare OpenAI

    try:
        response = client.chat.completions.create(
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


def process_query_results(engine, sql_query, openai_api_key):
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

        # ✅ Configurazione OpenAI per PandasAI
        llm = OpenAILLM(api_token=openai_api_key, model=AI_MODEL)
        sdf = SmartDataframe(df, config={"llm": llm})

        # ✅ Chiediamo all'AI di spiegare i dati senza grafici
        risposta = sdf.chat("Descrivi questi dati in modo chiaro e utile nella lingua dell'utente che fa la domanda.")

        # ✅ Chiediamo all'AI di generare codice Matplotlib per i grafici
        codice_grafico = sdf.chat("""Genera codice Matplotlib per visualizzare i dati,
            in un modo significativo ed efficace,
            tutti con testi ed etichette nella lingua dell'utente che fa la domanda."
            Produci almeno 2 visualizzazioni per aumentare la leggibilità del dato.
            Restituisci solo codice Python per creare i grafici, senza spiegazioni o testo aggiuntivo
            così da poterlo eseguire con excec().
            Usa `dfs = pd.DataFrame(data)` per definire il DataFrame.
            Assicurati che `dfs` sia sempre un DataFrame Pandas.""")

        # ✅ Eseguiamo il codice Matplotlib per creare i grafici
        grafici_base64 = []
        try:
            local_vars = {}
            exec(codice_grafico, {"plt": plt}, local_vars)  # ✅ Eseguiamo il codice AI in un ambiente sicuro
            figs = [v for v in local_vars.values() if isinstance(v, plt.Figure)]

            for fig in figs:
                grafici_base64.append(encode_figure_to_base64(fig))

        except Exception as e:
            grafici_base64 = []
            print(f"❌ codice Matplotlib generato dall'AI: {codice_grafico}")
            print(f"❌ Errore nell'esecuzione del codice Matplotlib generato dall'AI: {e}")

        return {
            "descrizione": risposta,
            "dati": df.to_dict(orient="records"),
            "grafici": grafici_base64  # ✅ Restituiamo i grafici generati dall'AI
        }

    except Exception as e:
        return {
            "errore": f"❌ Errore nell'elaborazione dei dati: {str(e)}",
            "descrizione": "❌ Errore nell'analisi.",
            "dati": [],
            "grafici": []
        }
