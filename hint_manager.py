"""
Gestore per gli hint di interpretazione dati.
Questo modulo gestisce la raccolta, il salvataggio e il recupero degli hint
che l'utente fornisce per guidare l'AI nell'interpretazione dei dati.
"""
import json
import os
import logging
from sqlalchemy import Column, Integer, String, Text, create_engine  # type: ignore
from sqlalchemy.orm import sessionmaker, declarative_base  # type: ignore
from datetime import datetime

# Configura il logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Definizione del modello del database
Base = declarative_base()

# Percorso del database
DB_PATH = "sqlite:///cache/hint_store.db"
HINTS_FILE = "cache/hints.json"

# Assicurati che la directory esista
os.makedirs("cache", exist_ok=True)


class DataHint(Base):
    """Modello per la tabella degli hint sui dati."""
    __tablename__ = "data_hints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(String, default=lambda: datetime.now().isoformat())
    updated_at = Column(String, default=lambda: datetime.now().isoformat(), onupdate=lambda: datetime.now().isoformat())
    hint_text = Column(Text, nullable=False)
    hint_category = Column(String, default="generale")  # es. "generale", "tabella:ordini", "colonna:data_ordine"
    active = Column(Integer, default=1)  # 1 = attivo, 0 = disattivato

    def __repr__(self):
        return f"<DataHint(id='{self.id}', category='{self.hint_category}', text='{self.hint_text[:30]}...')>"


# Inizializzazione del database
engine = create_engine(DB_PATH)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


def add_hint(hint_text, hint_category="generale"):
    """
    Aggiunge un nuovo hint al database.

    Args:
        hint_text (str): Il testo dell'hint
        hint_category (str): La categoria dell'hint (default: "generale")

    Returns:
        int: L'ID dell'hint inserito
    """
    try:
        session = Session()
        hint = DataHint(hint_text=hint_text, hint_category=hint_category)
        session.add(hint)
        session.commit()
        hint_id = hint.id
        session.close()
        logger.info(f"✅ Aggiunto nuovo hint (ID: {hint_id}, Categoria: {hint_category})")
        return hint_id
    except Exception as e:
        logger.error(f"❌ Errore nell'aggiunta dell'hint: {e}")
        return None


def update_hint(hint_id, hint_text=None, hint_category=None, active=None):
    """
    Aggiorna un hint esistente.

    Args:
        hint_id (int): L'ID dell'hint da aggiornare
        hint_text (str, optional): Il nuovo testo dell'hint
        hint_category (str, optional): La nuova categoria dell'hint
        active (int, optional): Lo stato dell'hint (1 = attivo, 0 = disattivato)

    Returns:
        bool: True se l'aggiornamento è riuscito, False altrimenti
    """
    try:
        session = Session()
        hint = session.query(DataHint).filter_by(id=hint_id).first()

        if hint:
            if hint_text is not None:
                hint.hint_text = hint_text
            if hint_category is not None:
                hint.hint_category = hint_category
            if active is not None:
                hint.active = active

            hint.updated_at = datetime.now().isoformat()
            session.commit()
            session.close()
            logger.info(f"✅ Aggiornato hint (ID: {hint_id})")
            return True
        else:
            session.close()
            logger.warning(f"⚠️ Hint non trovato (ID: {hint_id})")
            return False
    except Exception as e:
        logger.error(f"❌ Errore nell'aggiornamento dell'hint: {e}")
        return False


def delete_hint(hint_id):
    """
    Elimina un hint dal database.

    Args:
        hint_id (int): L'ID dell'hint da eliminare

    Returns:
        bool: True se l'eliminazione è riuscita, False altrimenti
    """
    try:
        session = Session()
        hint = session.query(DataHint).filter_by(id=hint_id).first()

        if hint:
            session.delete(hint)
            session.commit()
            session.close()
            logger.info(f"✅ Eliminato hint (ID: {hint_id})")
            return True
        else:
            session.close()
            logger.warning(f"⚠️ Hint non trovato (ID: {hint_id})")
            return False
    except Exception as e:
        logger.error(f"❌ Errore nell'eliminazione dell'hint: {e}")
        return False


def toggle_hint_status(hint_id):
    """
    Attiva/disattiva un hint.

    Args:
        hint_id (int): L'ID dell'hint da attivare/disattivare

    Returns:
        bool: True se l'operazione è riuscita, False altrimenti
    """
    try:
        session = Session()
        hint = session.query(DataHint).filter_by(id=hint_id).first()

        if hint:
            # Toggle lo stato (1 -> 0, 0 -> 1)
            hint.active = 1 - hint.active
            hint.updated_at = datetime.now().isoformat()

            session.commit()
            session.close()
            logger.info(f"✅ Cambiato stato hint (ID: {hint_id}, Stato: {'attivo' if hint.active else 'disattivato'})")
            return True
        else:
            session.close()
            logger.warning(f"⚠️ Hint non trovato (ID: {hint_id})")
            return False
    except Exception as e:
        logger.error(f"❌ Errore nel cambio di stato dell'hint: {e}")
        return False


def get_all_hints():
    """
    Recupera tutti gli hint dal database.

    Returns:
        list: Lista di tutti gli hint
    """
    try:
        session = Session()
        hints = session.query(DataHint).all()
        session.close()

        return [
            {
                "id": hint.id,
                "created_at": hint.created_at,
                "updated_at": hint.updated_at,
                "hint_text": hint.hint_text,
                "hint_category": hint.hint_category,
                "active": hint.active
            }
            for hint in hints
        ]
    except Exception as e:
        logger.error(f"❌ Errore nel recupero degli hint: {e}")
        return []


def get_active_hints():
    """
    Recupera solo gli hint attivi dal database.

    Returns:
        list: Lista degli hint attivi
    """
    try:
        session = Session()
        hints = session.query(DataHint).filter_by(active=1).all()
        session.close()

        return [
            {
                "id": hint.id,
                "created_at": hint.created_at,
                "updated_at": hint.updated_at,
                "hint_text": hint.hint_text,
                "hint_category": hint.hint_category,
                "active": hint.active
            }
            for hint in hints
        ]
    except Exception as e:
        logger.error(f"❌ Errore nel recupero degli hint attivi: {e}")
        return []


def get_hint_by_id(hint_id):
    """
    Recupera un hint specifico per ID.

    Args:
        hint_id (int): L'ID dell'hint da recuperare

    Returns:
        dict: L'hint richiesto o None se non trovato
    """
    try:
        session = Session()
        hint = session.query(DataHint).filter_by(id=hint_id).first()
        session.close()

        if hint:
            return {
                "id": hint.id,
                "created_at": hint.created_at,
                "updated_at": hint.updated_at,
                "hint_text": hint.hint_text,
                "hint_category": hint.hint_category,
                "active": hint.active
            }
        else:
            return None
    except Exception as e:
        logger.error(f"❌ Errore nel recupero dell'hint (ID: {hint_id}): {e}")
        return None


def format_hints_for_prompt():
    """
    Formatta tutti gli hint attivi per l'inclusione nel prompt.

    Returns:
        str: Gli hint formattati pronti per essere inseriti nel prompt
    """
    active_hints = get_active_hints()

    if not active_hints:
        return ""

    # Raggruppa gli hint per categoria
    hints_by_category = {}
    for hint in active_hints:
        category = hint["hint_category"]
        if category not in hints_by_category:
            hints_by_category[category] = []
        hints_by_category[category].append(hint["hint_text"])

    # Formatta gli hint
    formatted_hints = ["**Istruzioni per l'interpretazione dei dati:**"]

    # Prima aggiungiamo gli hint generali
    if "generale" in hints_by_category:
        for hint in hints_by_category["generale"]:
            formatted_hints.append(f"- {hint}")
        del hints_by_category["generale"]

    # Poi aggiungiamo gli hint specifici per tabella o colonna
    for category, hints in hints_by_category.items():
        formatted_hints.append(f"\n**{category.capitalize()}:**")
        for hint in hints:
            formatted_hints.append(f"- {hint}")

    return "\n".join(formatted_hints)


def export_hints_to_json():
    """
    Esporta tutti gli hint in un file JSON.

    Returns:
        bool: True se l'esportazione è riuscita, False altrimenti
    """
    try:
        hints = get_all_hints()

        with open(HINTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(hints, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ Esportati {len(hints)} hint in {HINTS_FILE}")
        return True
    except Exception as e:
        logger.error(f"❌ Errore nell'esportazione degli hint: {e}")
        return False


def import_hints_from_json():
    """
    Importa gli hint da un file JSON.

    Returns:
        bool: True se l'importazione è riuscita, False altrimenti
    """
    try:
        if not os.path.exists(HINTS_FILE):
            logger.warning(f"⚠️ File {HINTS_FILE} non trovato")
            return False

        with open(HINTS_FILE, 'r', encoding='utf-8') as f:
            hints = json.load(f)

        session = Session()

        # Elimina tutti gli hint esistenti
        session.query(DataHint).delete()

        # Aggiungi i nuovi hint
        for hint in hints:
            new_hint = DataHint(
                hint_text=hint["hint_text"],
                hint_category=hint["hint_category"],
                active=hint["active"],
                created_at=hint.get("created_at", datetime.now().isoformat()),
                updated_at=hint.get("updated_at", datetime.now().isoformat())
            )
            session.add(new_hint)

        session.commit()
        session.close()

        logger.info(f"✅ Importati {len(hints)} hint da {HINTS_FILE}")
        return True
    except Exception as e:
        logger.error(f"❌ Errore nell'importazione degli hint: {e}")
        return False
