"""
Sistema di gestione degli hint per l'interpretazione dei dati.
Gestisce il salvataggio, il recupero e l'aggiornamento degli hint
che l'utente fornisce per guidare l'AI nell'interpretazione dei dati.
"""
import json
import os
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, create_engine  # type: ignore
from sqlalchemy.orm import sessionmaker, declarative_base  # type: ignore
from backend.utils.logging import get_logger
from backend.config import HINT_DB_URL, HINTS_FILE

logger = get_logger(__name__)

# Definizione del modello del database
Base = declarative_base()


class DataHint(Base):
    """Modello per la tabella degli hint sui dati."""
    __tablename__ = "data_hints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(String, default=lambda: datetime.now().isoformat())
    updated_at = Column(String, default=lambda: datetime.now(
    ).isoformat(), onupdate=lambda: datetime.now().isoformat())
    hint_text = Column(Text, nullable=False)
    # es. "generale", "tabella:ordini", "colonna:data_ordine"
    hint_category = Column(String, default="generale")
    active = Column(Integer, default=1)  # 1 = attivo, 0 = disattivato

    def __repr__(self):
        return f"<DataHint(id='{self.id}', category='{self.hint_category}', text='{self.hint_text[:30]}...')>"


class HintCategory(Base):
    """Modello per la tabella delle categorie di hint."""
    __tablename__ = "hint_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    # postgresql, sqlserver, null=tutti
    db_type = Column(String, nullable=True)
    created_at = Column(String, default=lambda: datetime.now().isoformat())

    def __repr__(self):
        return f"<HintCategory(id='{self.id}', name='{self.name}')>"


class HintStore:
    """Gestisce il database degli hint."""

    def __init__(self, db_url=HINT_DB_URL):
        """
        Inizializza il database degli hint.

        Args:
            db_url (str): URL di connessione al database
        """
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def add_hint(self, hint_text, hint_category="generale"):
        """
        Aggiunge un nuovo hint al database.

        Args:
            hint_text (str): Il testo dell'hint
            hint_category (str): La categoria dell'hint (default: "generale")

        Returns:
            int: L'ID dell'hint inserito
        """
        try:
            session = self.Session()
            hint = DataHint(hint_text=hint_text, hint_category=hint_category)
            session.add(hint)
            session.commit()
            hint_id = hint.id
            session.close()
            logger.info(
                f"✅ Aggiunto nuovo hint (ID: {hint_id}, Categoria: {hint_category})")
            return hint_id
        except Exception as e:
            logger.error(f"❌ Errore nell'aggiunta dell'hint: {e}")
            return None

    def update_hint(self, hint_id, hint_text=None, hint_category=None, active=None):
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
            session = self.Session()
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

    def delete_hint(self, hint_id):
        """
        Elimina un hint dal database.

        Args:
            hint_id (int): L'ID dell'hint da eliminare

        Returns:
            bool: True se l'eliminazione è riuscita, False altrimenti
        """
        try:
            session = self.Session()
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

    def toggle_hint_status(self, hint_id):
        """
        Attiva/disattiva un hint.

        Args:
            hint_id (int): L'ID dell'hint da attivare/disattivare

        Returns:
            bool: True se l'operazione è riuscita, False altrimenti
        """
        try:
            session = self.Session()
            hint = session.query(DataHint).filter_by(id=hint_id).first()

            if hint:
                # Toggle lo stato (1 -> 0, 0 -> 1)
                hint.active = 1 - hint.active
                hint.updated_at = datetime.now().isoformat()

                session.commit()
                session.close()
                logger.info(
                    f"✅ Cambiato stato hint (ID: {hint_id}, Stato: {'attivo' if hint.active else 'disattivato'})")
                return True
            else:
                session.close()
                logger.warning(f"⚠️ Hint non trovato (ID: {hint_id})")
                return False
        except Exception as e:
            logger.error(f"❌ Errore nel cambio di stato dell'hint: {e}")
            return False

    def get_all_hints(self):
        """
        Recupera tutti gli hint dal database.

        Returns:
            list: Lista di tutti gli hint
        """
        try:
            session = self.Session()
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

    def get_active_hints(self, filter_hint_category=None):
        """
        Recupera solo gli hint attivi dal database.

        Args:
            filter_hint_category (str, optional): Filtra per categoria

        Returns:
            list: Lista degli hint attivi
        """
        try:
            session = self.Session()
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
                for hint in hints if (filter_hint_category is None or
                                      hint.hint_category in [filter_hint_category, "generale"])
            ]
        except Exception as e:
            logger.error(f"❌ Errore nel recupero degli hint attivi: {e}")
            return []

    def get_hint_by_id(self, hint_id):
        """
        Recupera un hint specifico per ID.

        Args:
            hint_id (int): L'ID dell'hint da recuperare

        Returns:
            dict: L'hint richiesto o None se non trovato
        """
        try:
            session = self.Session()
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
            logger.error(
                f"❌ Errore nel recupero dell'hint (ID: {hint_id}): {e}")
            return None

    def format_hints_for_prompt(self, filter_category=None):
        """
        Formatta tutti gli hint attivi per l'inclusione nel prompt.

        Args:
            filter_category (str, optional): Categoria per filtrare gli hint

        Returns:
            str: Gli hint formattati pronti per essere inseriti nel prompt
        """
        active_hints = self.get_active_hints(filter_category)

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

    def export_hints_to_json(self, filepath=HINTS_FILE):
        """
        Esporta tutti gli hint in un file JSON.

        Args:
            filepath (str, optional): Percorso del file di output

        Returns:
            bool: True se l'esportazione è riuscita, False altrimenti
        """
        try:
            hints = self.get_all_hints()

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(hints, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ Esportati {len(hints)} hint in {filepath}")
            return True
        except Exception as e:
            logger.error(f"❌ Errore nell'esportazione degli hint: {e}")
            return False

    def import_hints_from_json(self, filepath=HINTS_FILE):
        """
        Importa gli hint da un file JSON.

        Args:
            filepath (str, optional): Percorso del file da importare

        Returns:
            bool: True se l'importazione è riuscita, False altrimenti
        """
        try:
            if not os.path.exists(filepath):
                logger.warning(f"⚠️ File {filepath} non trovato")
                return False

            with open(filepath, 'r', encoding='utf-8') as f:
                hints = json.load(f)

            session = self.Session()

            # Elimina tutti gli hint esistenti
            session.query(DataHint).delete()

            # Aggiungi i nuovi hint
            for hint in hints:
                new_hint = DataHint(
                    hint_text=hint["hint_text"],
                    hint_category=hint["hint_category"],
                    active=hint["active"],
                    created_at=hint.get(
                        "created_at", datetime.now().isoformat()),
                    updated_at=hint.get(
                        "updated_at", datetime.now().isoformat())
                )
                session.add(new_hint)

            session.commit()
            session.close()

            logger.info(f"✅ Importati {len(hints)} hint da {filepath}")
            return True
        except Exception as e:
            logger.error(f"❌ Errore nell'importazione degli hint: {e}")
            return False

    def get_all_categories(self):
        """
        Recupera tutte le categorie salvate nel database.

        Returns:
            list: Lista di tutte le categorie
        """
        try:
            session = self.Session()
            categories = session.query(HintCategory).all()
            session.close()

            # Aggiungi "generale" se non esiste
            category_names = [category.name for category in categories]
            if "generale" not in category_names and categories:
                # Aggiungi "generale" all'inizio della lista
                return ["generale"] + category_names

            return category_names if categories else ["generale"]
        except Exception as e:
            logger.error(f"❌ Errore nel recupero delle categorie: {e}")
            return ["generale"]  # Ritorna almeno la categoria default

    def add_category(self, category_name, description="", db_type=None):
        """
        Aggiunge una nuova categoria al database.

        Args:
            category_name (str): Nome della nuova categoria
            description (str): Descrizione della categoria
            db_type (str): Tipo di database associato (postgresql, sqlserver, None=tutti)

        Returns:
            bool: True se l'aggiunta è riuscita, False se la categoria esiste già
        """
        try:
            session = self.Session()

            # Verifica se la categoria esiste già
            existing = session.query(HintCategory).filter_by(
                name=category_name).first()
            if existing:
                session.close()
                logger.warning(f"⚠️ La categoria '{category_name}' esiste già")
                return False

            # Crea la nuova categoria
            new_category = HintCategory(
                name=category_name,
                description=description,
                db_type=db_type
            )

            session.add(new_category)
            session.commit()
            session.close()

            logger.info(f"✅ Aggiunta nuova categoria: {category_name}")
            return True
        except Exception as e:
            if 'session' in locals():
                session.rollback()
                session.close()
            logger.error(f"❌ Errore nell'aggiunta della categoria: {e}")
            return False

    def delete_category(self, category_name, replace_with="generale"):
        """
        Elimina una categoria e aggiorna tutti gli hint associati.

        Args:
            category_name (str): Nome della categoria da eliminare
            replace_with (str): Nome della categoria con cui sostituire

        Returns:
            int: Numero di hint aggiornati, o -1 in caso di errore
        """
        try:
            # Non permettiamo di eliminare la categoria "generale"
            if category_name == "generale":
                logger.warning(
                    "⚠️ Non è possibile eliminare la categoria 'generale'")
                return 0

            session = self.Session()

            # Verifica che la categoria esista
            category = session.query(HintCategory).filter_by(
                name=category_name).first()
            if not category:
                session.close()
                logger.warning(f"⚠️ Categoria '{category_name}' non trovata")
                return 0

            # Verifica che la categoria di sostituzione esista
            if replace_with != "generale":
                replacement = session.query(HintCategory).filter_by(
                    name=replace_with).first()
                if not replacement:
                    session.close()
                    logger.warning(
                        f"⚠️ Categoria di sostituzione '{replace_with}' non trovata")
                    return -1

            # Aggiorna gli hint che usano questa categoria
            affected_rows = session.query(DataHint).filter_by(hint_category=category_name).update(
                {"hint_category": replace_with}
            )

            # Elimina la categoria
            session.delete(category)

            session.commit()
            session.close()

            logger.info(
                f"✅ Eliminata categoria '{category_name}', {affected_rows} hint aggiornati")
            return affected_rows
        except Exception as e:
            if 'session' in locals():
                session.rollback()
                session.close()
            logger.error(f"❌ Errore nell'eliminazione della categoria: {e}")
            return -1
