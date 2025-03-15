# Database Crawler AI 🚀

## 📌 Panoramica

**Database Crawler AI** è un'applicazione basata su **FastAPI** e **Streamlit** che permette di: ✅ Generare query SQL in linguaggio naturale con OpenAI 🎯 ✅ Recuperare la struttura del database (tabelle, colonne, chiavi esterne, indici e commenti) 🗄️ ✅ Fornire analisi descrittive e visualizzazioni sui dati 📊 ✅ Permettere il download dei dati in Excel 📥 ✅ Collegarsi a un database PostgreSQL tramite un **tunnel SSH** 🔒

## 🛠️ Stack Tecnologico

- **Backend:** FastAPI + SQLAlchemy + OpenAI API
- **Frontend:** Streamlit
- **Database:** PostgreSQL (accesso via tunnel SSH)
- **AI:** OpenAI GPT-4o-mini + PandasAI
- **Containerizzazione:** Docker + Docker Compose

---

## 🚀 Installazione e Setup

### 📥 1. Clona il repository

```bash
git clone https://github.com/tuo-utente/database_crawler_ai.git
cd database_crawler_ai
```

### 📦 2. Configura le variabili d'ambiente

Crea un file `` nella root del progetto e inserisci:

```env
OPENAI_API_KEY=tuo_openai_api_key
DATABASE_URL=postgresql://user:password@db:5432/nome_database
SSH_HOST=10.11.11.4
SSH_USER=tuo_utente_ssh
SSH_KEY=~/.ssh/id_rsa
```

### 🐳 3. Avvia l'applicazione con Docker

```bash
docker-compose up --build
```

L'applicazione sarà accessibile ai seguenti indirizzi:

- **Frontend (Streamlit):** [http://localhost:8501](http://localhost:8501)
- **Backend (FastAPI):** [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger API Docs)

---

## 🎮 Utilizzo

### 1️⃣ Accedi al Frontend 📺

Apri [http://localhost:8501](http://localhost:8501) e: ✅ Inserisci i dettagli della connessione **PostgreSQL** e **SSH** 🔐 ✅ Scrivi una domanda in linguaggio naturale (es. *"Mostrami il totale delle vendite per categoria"*) 📝 ✅ L'AI genererà la query SQL, eseguirà l'analisi e visualizzerà i risultati 🏆 ✅ Scarica i dati in **Excel** o visualizza i **grafici generati** 📈

### 2️⃣ Aggiornare la struttura del database 🔄

Clicca su **"Riscansiona Database"** nel frontend per aggiornare: ✅ Tabelle, colonne e chiavi esterne 🔗 ✅ Indici e commenti delle colonne 📌

---

## 📂 Struttura della Codebase
```
📦 database_crawler_ai
├── 📄 app.py               # Backend FastAPI per gestione query
├── 📄 frontend.py          # Interfaccia utente Streamlit
├── 📄 query_ai.py          # Generazione di query SQL con OpenAI
├── 📄 query_cache.py       # Gestione cache delle query SQL
├── 📄 db_schema.py         # Estratto e cache della struttura del database
├── 📄 database.py          # Configurazione e gestione del database SQLite
├── 📄 requirements.txt     # Librerie necessarie
├── 📄 docker-compose.yml   # Configurazione Docker
└── 📄 Dockerfile           # Dockerfile per il backend
```

---

## 🛠️ API Endpoints

📡 L'API backend espone i seguenti endpoint:

### 🔍 **Genera ed esegui query SQL**

```http
POST /query
```

**Request JSON:**

```json
{
  "domanda": "Mostrami il totale delle vendite per categoria",
  "openai_api_key": "tuo_openai_api_key",
  "ssh_config": {
    "ssh_host": "10.11.11.4",
    "ssh_user": "tuo_utente_ssh",
    "ssh_key": "~/.ssh/id_rsa"
  },
  "db_config": {
    "host": "127.0.0.1",
    "port": "5432",
    "user": "admin",
    "password": "admin",
    "database": "vendite"
  },
  "force_no_cache": false
}
```

### 🔄 **Aggiorna la struttura del database**

```http
POST /refresh_schema
```

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

---

## 🛠️ Troubleshooting

### ❌ **Errore di connessione al database**

✅ Verifica che il tunnel SSH sia attivo con:

```bash
ssh -i ~/.ssh/id_rsa tuo_utente_ssh@10.11.11.4
```

✅ Controlla che le credenziali PostgreSQL siano corrette

### ❌ **Errore OpenAI (modello non disponibile)**

✅ Assicurati di usare un modello valido, es: `gpt-4o-mini`

---

## 🚀 Contribuire

Se vuoi migliorare il progetto:

1. Fai un **fork** di questo repository
2. Crea un **branch** con la tua modifica: `git checkout -b mia-modifica`
3. Fai un **commit**: `git commit -m "Aggiunto supporto per XYZ"`
4. Manda una **Pull Request** 🚀

---

## 📝 Licenza

Distribuito sotto licenza **MIT**. Sentiti libero di usare e migliorare questo progetto! 😊

