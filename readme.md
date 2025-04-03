
# 🧠 Database Crawler AI

**Database Crawler AI** è un'applicazione modulare progettata per interagire con database relazionali tramite linguaggio naturale. Utilizza modelli LLM (Large Language Models) per generare, interpretare e ottimizzare query SQL. Include funzionalità avanzate di caching, logging, gestione degli hint e una semplice interfaccia frontend.

## 🚀 Funzionalità Principali

- 🔗 Connessione a database tramite driver ODBC (configurabili via `odbc.ini`)
- 💬 Interpretazione in linguaggio naturale delle richieste utente e conversione in SQL
- 🧠 Integrazione con modelli LLM personalizzabili (`llm_manager.py`)
- ⚙️ Gestione dello schema del database (`db_schema.py`) per facilitare la comprensione da parte del modello AI
- ⚡ Caching intelligente delle query (`query_cache.py`)
- ✨ Generazione automatica di hint e ottimizzazioni (`hint_manager.py`)
- 🐳 Supporto Docker per il deployment rapido
- 🌐 Frontend minimale (`frontend.py`) per demo o uso diretto
- 📋 Esempi pratici (`examples.md`)

## 🛠️ Stack Tecnologico

- **Backend:** FastAPI + SQLAlchemy
- **Frontend:** Streamlit
- **Database:** PostgreSQL o SQL Server (accesso via tunnel SSH)
- **AI:** OpenAI, Deepseek, Anthropic
- **Containerizzazione:** Docker + Docker Compose

## 📁 Struttura del Progetto

```
database_crawler_ai/
├── config.py               # Configurazione centrale dell'app
├── database.py             # Gestione connessione e interfaccia col DB
├── db_schema.py            # Parsing dello schema del database
├── query_ai.py             # Logica di generazione/interazione SQL-AI
├── llm_manager.py          # Gestione dei modelli LLM
├── hint_manager.py         # Sistema di suggerimenti e miglioramenti query
├── query_cache.py          # Caching delle query per performance
├── frontend.py             # Interfaccia frontend semplice
├── requirements.txt        # Dipendenze Python
├── Dockerfile              # Docker container setup
├── odbc.ini / odbcinst.ini # Configurazione driver ODBC
├── examples.md             # Esempi di utilizzo
└── pandasai.log            # File di log operativo
```

## 🛠️ Installazione

1. **Clona il repository:**
   ```bash
   git clone https://github.com/tuo-utente/database-crawler-ai.git
   cd database-crawler-ai
   ```

2. **Crea un ambiente virtuale:**
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. **Installa le dipendenze:**
   ```bash
   pip install -r requirements.txt
   ```

4. **(Opzionale) Esegui in Docker:**
   ```bash
   docker build -t crawler-ai .
   docker run -p 8000:8000 crawler-ai
   ```

## ⚙️ Configurazione

- Imposta le connessioni ODBC nei file `odbc.ini` e `odbcinst.ini`.
- Modifica `config.py` per i tuoi parametri di connessione, modelli LLM e opzioni runtime.
- Puoi definire i tuoi modelli LLM nel modulo `llm_manager.py`.

## 📌 Esempio d'Uso

```python
from query_ai import execute_nl_query

response = execute_nl_query("Qual è il totale delle vendite nel 2024?")
print(response.sql_query)    # Mostra la query SQL generata
print(response.result)       # Mostra il risultato della query
```

Consulta `examples.md` per ulteriori esempi e scenari reali.

## 💡 Sistema di Hint

Il modulo `hint_manager.py` fornisce un sistema avanzato per la generazione automatica di suggerimenti contestuali (hint) volti a migliorare le query SQL prodotte. Tra le funzionalità:

- Analisi del contesto semantico della richiesta utente
- Generazione di suggerimenti per affinare la query
- Integrazione con i modelli LLM per ottimizzare la precisione
- Possibilità di estendere regole e logiche di hint personalizzati

Questo modulo è particolarmente utile in ambienti in cui le query devono essere spiegabili o migliorabili in modo iterativo.

## 🔁 Sistema di Retry con Ottimizzazione Automatica

Il sistema include una logica di **retry intelligente** per le query SQL generate, pensata per massimizzare l’affidabilità anche in presenza di errori di esecuzione.

### ⚙️ Funzionamento

1. **Analisi dell'errore SQL**: Se una query generata fallisce, l'errore restituito dal database viene catturato e analizzato.
2. **Forward dell’errore al LLM**: L'errore viene inoltrato come feedback al modello LLM insieme alla query originale e al contesto.
3. **Rigenerazione della query**: Il modello tenta di generare una nuova versione corretta della query sulla base dell’errore ricevuto.
4. **Secondo tentativo automatico**: La query corretta viene eseguita automaticamente senza intervento umano.

### ✅ Vantaggi

- Migliore resilienza in ambienti dinamici
- Riduzione degli errori fatali in fase di runtime
- Adattabilità a strutture dati complesse e nomi tabella non standard
- Comportamento trasparente per l’utente finale

Questa funzionalità è utile sia in ambienti di test che in produzione, dove l’interpretazione automatica degli errori consente al sistema di apprendere iterativamente.


## 🚀 Gestione della Cache
### 1️⃣ **Cache delle Query SQL**
Il sistema salva le query SQL generate dall'AI in **SQLite**, riducendo il numero di chiamate a OpenAI.
- **Matching con AI**: Le nuove domande vengono confrontate con quelle già esistenti tramite il modello **SentenceTransformers**.
- **Indice FAISS**: Accelera la ricerca delle domande più simili.
- **Indice su `db_hash`**: Filtra direttamente nel database per evitare confronti inutili.

📌 **Forzare una nuova query**: L'utente può scegliere di ignorare la cache selezionando un'opzione nell'interfaccia.

### 2️⃣ **Cache della Struttura del Database**
Per evitare di interrogare il database a ogni richiesta, la struttura viene **salvata in un file JSON**. Se il database cambia:
- Il sistema rigenera l'hash della struttura e invalida la cache.
- Le query salvate vengono ignorate se non sono più coerenti con il database attuale.

## 🧪 Testing

L’infrastruttura di test non è ancora inclusa. Puoi comunque testare i moduli con `pytest` o strumenti simili. Per debugging, consulta `pandasai.log`.

