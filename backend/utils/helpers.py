"""
Funzioni di utilità generiche.
"""
import io
import base64
import os
from datetime import datetime
import re
from backend.utils.logging import get_logger

logger = get_logger(__name__)


def encode_figure_to_base64(fig):
    """
    Converte un oggetto Matplotlib Figure in una stringa Base64 per inviarlo al frontend.

    Args:
        fig (matplotlib.figure.Figure): Figura Matplotlib da convertire

    Returns:
        str: Stringa Base64 che rappresenta l'immagine
    """
    img_bytes = io.BytesIO()
    fig.savefig(img_bytes, format="png", bbox_inches="tight")
    img_bytes.seek(0)
    return base64.b64encode(img_bytes.read()).decode("utf-8")


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

            if inside_code_block or "```" not in query_sql:
                cleaned_lines.append(line)

        query_sql = "\n".join(cleaned_lines)

    # Rimuovi eventuali prefissi "sql" all'inizio della query
    query_sql = query_sql.strip()
    if query_sql.lower().startswith("sql"):
        query_sql = query_sql[3:].strip()

    return query_sql


def clean_generated_code(code):
    """
    Rimuove le righe ` ```python ` e ` ``` ` dal codice generato.

    Args:
        code (str): Codice potenzialmente contenente marcatori markdown

    Returns:
        str: Codice pulito
    """
    lines = code.strip().split("\n")

    # Se il codice inizia con ```python o ```other_lang, rimuoviamo la prima riga
    if lines and lines[0].startswith("```"):
        lines = lines[1:]

    # Se il codice termina con ```, rimuoviamo l'ultima riga
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    return "\n".join(lines)


def generate_timestamp():
    """
    Genera un timestamp formattato per i nomi dei file.

    Returns:
        str: Timestamp in formato "YYYYMMDD_HHMMSS"
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def sanitize_filename(name):
    """
    Sanitizza un nome per renderlo valido come nome file.

    Args:
        name (str): Nome potenzialmente contenente caratteri non validi

    Returns:
        str: Nome file sanitizzato
    """
    # Rimuovi caratteri non validi nei nomi file
    s = re.sub(r'[^\w\s-]', '', name).strip()
    # Sostituisci spazi bianchi con underscore
    s = re.sub(r'[-\s]+', '_', s)
    return s[:100]  # Limita lunghezza


def save_chart(fig, name, output_dir):
    """
    Salva un grafico Matplotlib come immagine.

    Args:
        fig (matplotlib.figure.Figure): Figura da salvare
        name (str): Nome base per il file
        output_dir (str): Directory di output

    Returns:
        str: Percorso del file salvato
    """
    sanitized_name = sanitize_filename(name)
    timestamp = generate_timestamp()
    filename = f"{sanitized_name}_{timestamp}.png"
    filepath = os.path.join(output_dir, filename)

    try:
        fig.savefig(filepath, bbox_inches="tight", dpi=300)
        logger.info(f"Grafico salvato: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Errore nel salvataggio del grafico: {e}")
        return ""
