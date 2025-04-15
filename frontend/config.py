"""
Configurazioni e costanti globali per l'applicazione frontend.
Centralizza parametri, impostazioni e valori predefiniti.
"""
import os
from dotenv import load_dotenv  # type: ignore

# Carica variabili d'ambiente
load_dotenv()

# Costanti dell'applicazione
APP_TITLE = "L'AI che lavora per la tua lavanderia"
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
CREDENTIALS_FILE = os.getenv("CREDENTIALS_FILE", "/app/credentials.json")
PROFILES_FILE = os.getenv("PROFILES_FILE", "/app/cache/connection_profiles.json")

# Configurazione dei provider LLM
LLM_PROVIDERS = {
    "openai": {"name": "OpenAI", "api_key_name": "openai_api_key", "requires_secret": False},
    "claude": {"name": "Anthropic Claude", "api_key_name": "claude_api_key", "requires_secret": False},
    "deepseek": {"name": "DeepSeek", "api_key_name": "deepseek_api_key", "requires_secret": False},
    # "ernie": {"name": "Baidu ERNIE", "api_key_name": "ernie_api_key", "requires_secret": True,
    #           "secret_key_name": "ernie_secret_key"},
    "gemini": {"name": "Google Gemini", "api_key_name": "gemini_api_key", "requires_secret": False}
}

# Domande predefinite per diversi contesti
DOMANDE_SUGGERITE = {
    "montanari": [
        ("""Qual'è l'impianto di confezionamento che produce più quintail? """
         """fai una comparazione tra quelli presenti valutando le medie produttive degil ultimi 6 mesi"""),
        "Come si distribuiscono i prodotti per impianto di confezionamento?",
        "Qual'è la media oraria di produzione per impianto di confezionamento?",
        "Fai un'analisi sui picchi orari gionnalieri di produzione per giorno della settimana ed impianto di confezionamento",
        "Qual'è la media pacchi minuto di produzione per impianto di confezionamento degli ultimi 12 mesi?"
    ],
    "jit40": [
        "Mostrami l'andamento del fatturato dell'ultimo anno per categoria",
        "Quali sono stati i primi 5 prodotti più consegnati negli ultimi 6 mesi?",
        "Qual è la media dei prezzi unitari per categoria di prodotto venduto?",
        "Negli acquisti quali prodotti hanno subito maggiori aumenti nel 2024 rispetto al 2023?",
        "Qual'è, in quintali, il bollettato medio settimanale per ciascuna categoria?",
    ]
}

# Impostazioni predefinite di Streamlit
STREAMLIT_CONFIG = {
    "page_title": "JIT40 Laundry Bot",
    "page_icon": "🧠",
    "layout": "wide",
    "initial_sidebar_state": "expanded",
    "menu_items": {
        'About': APP_TITLE
    }
}
