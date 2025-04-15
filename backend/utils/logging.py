"""
Configurazione del sistema di logging dell'applicazione.
"""
import logging
import sys
from pathlib import Path
import os
from logging.handlers import RotatingFileHandler
from backend.config import CACHE_DIR, LOG_LEVEL

# Formato predefinito del log
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = os.path.join(CACHE_DIR, "crawler_ai.log")


def setup_logging():
    """
    Configura il sistema di logging con output su file e console.

    Returns:
        logging.Logger: Logger root configurato
    """
    # Crea la directory dei log se non esiste
    Path(os.path.dirname(LOG_FILE)).mkdir(parents=True, exist_ok=True)

    # Configura il logger root
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)

    # Svuota gli handler esistenti
    root_logger.handlers = []

    # Formatter comune
    formatter = logging.Formatter(LOG_FORMAT)

    # Handler per file con rotazione (10 file da 5MB ciascuno)
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=10
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Handler per console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Silenzia i logger troppo verbosi
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return root_logger


def get_logger(name):
    """
    Ottiene un logger configurato per un modulo specifico.

    Args:
        name (str): Nome del modulo che richiede il logger

    Returns:
        logging.Logger: Logger configurato
    """
    return logging.getLogger(name)
