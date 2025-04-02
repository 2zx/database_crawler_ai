FROM python:3.10

WORKDIR /app

# Installa le dipendenze per pymssql e pyodbc
RUN apt-get update && apt-get install -y \
    unixodbc \
    unixodbc-dev \
    freetds-dev \
    freetds-bin \
    tdsodbc \
    gnupg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Configurazione ODBC per SQL Server
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

# Verifica se streamlit è installato
RUN python -c "import streamlit"
