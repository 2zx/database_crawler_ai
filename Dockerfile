FROM python:3.10

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

# Verifica se streamlit è installato
RUN python -c "import streamlit"
