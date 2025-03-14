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
  }
}
```

### 🔄 **Aggiorna la struttura del database**

```http
POST /refresh_schema
```

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

