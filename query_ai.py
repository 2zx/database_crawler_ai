import pandas as pd
from sqlalchemy.sql import text
from openai import OpenAI
from pandasai import SmartDataframe
from pandasai.llm.openai import OpenAI as OpenAILLM


def generate_sql_query(domanda, db_schema, openai_api_key):
    """
    Genera una query SQL basata sulla domanda dell'utente e sulla struttura del database.

    :param domanda: La domanda dell'utente in linguaggio naturale
    :param db_schema: Dizionario contenente la struttura del database (tabelle, colonne, chiavi esterne)
    :param openai_api_key: La chiave API di OpenAI per la generazione della query
    :return: Una query SQL generata dall'AI
    """

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
            model="gpt-4o-mini",  # ✅ Usiamo gpt-4o-mini per generare query SQL
            messages=[
                {"role": "system", "content": "Sei un assistente SQL esperto."},
                {"role": "user", "content": prompt_sql}
            ]
        )

        sql_query = response.choices[0].message.content.strip()
        return sql_query

    except Exception as e:
        print(f"❌ Errore durante la generazione della query SQL: {e}")
        return None


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

        # ✅ Configurazione OpenAI per PandasAI
        llm = OpenAILLM(api_token=openai_api_key)
        sdf = SmartDataframe(df, config={"llm": llm})

        # ✅ Chiediamo all'AI di spiegare i dati senza grafici
        risposta = sdf.chat("Descrivi questi dati in modo chiaro e utile in italiano.")

        # ✅ Generiamo automaticamente i grafici
        grafici = sdf.chat("Genera i migliori grafici per questi dati e restituiscimi i risultati om array con i percorsi dei file.")

        return {
            "descrizione": risposta,
            "dati": df.to_dict(orient="records"),
            "grafici": grafici  # ✅ Restituiamo i grafici generati dall'AI
        }

    except Exception as e:
        return {
            "errore": f"❌ Errore nell'elaborazione dei dati: {str(e)}",
            "descrizione": "❌ Errore nell'analisi.",
            "dati": [],
            "grafici": []
        }
