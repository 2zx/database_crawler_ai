"""
Gestore per i profili di connessione al database.
Permette di salvare, caricare ed eliminare configurazioni di connessione riutilizzabili.
"""
import os
import json
import logging
from typing import Dict, List, Optional, Any

# Configura il logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConnectionProfileManager:
    """Gestisce i profili di connessione salvati."""

    def __init__(self, profiles_file: str):
        """
        Inizializza il gestore dei profili di connessione.

        Args:
            profiles_file (str): Percorso del file JSON dove salvare i profili
        """
        self.profiles_file = profiles_file
        self.profiles = self._load_profiles()

    def _load_profiles(self) -> Dict[str, Dict[str, Any]]:
        """
        Carica i profili dal file JSON.

        Returns:
            Dict: Dizionario dei profili salvati
        """
        if os.path.exists(self.profiles_file):
            try:
                with open(self.profiles_file, "r") as file:
                    profiles = json.load(file)
                logger.info(f"✅ Caricati {len(profiles)} profili di connessione")
                return profiles
            except Exception as e:
                logger.error(f"❌ Errore nel caricamento dei profili: {e}")
                return {}
        else:
            logger.info("🆕 Nessun profilo esistente, creato nuovo storage")
            return {}

    def _save_profiles(self) -> bool:
        """
        Salva i profili nel file JSON.

        Returns:
            bool: True se l'operazione è riuscita, False altrimenti
        """
        try:
            # Assicuriamoci che la directory esista
            os.makedirs(os.path.dirname(self.profiles_file), exist_ok=True)

            with open(self.profiles_file, "w") as file:
                json.dump(self.profiles, file, indent=2)
            logger.info(f"✅ Salvati {len(self.profiles)} profili di connessione")
            return True
        except Exception as e:
            logger.error(f"❌ Errore nel salvataggio dei profili: {e}")
            return False

    def get_profile_names(self) -> List[str]:
        """
        Restituisce la lista dei nomi dei profili disponibili.

        Returns:
            List[str]: Lista dei nomi dei profili
        """
        return list(self.profiles.keys())

    def get_profile(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """
        Restituisce un profilo specifico.

        Args:
            profile_name (str): Nome del profilo da recuperare

        Returns:
            Dict or None: Configurazione del profilo o None se non esiste
        """
        return self.profiles.get(profile_name)

    def save_profile(self, profile_name: str, config: Dict[str, Any]) -> bool:
        """
        Salva un nuovo profilo o aggiorna uno esistente.

        Args:
            profile_name (str): Nome del profilo
            config (Dict): Configurazione da salvare

        Returns:
            bool: True se l'operazione è riuscita, False altrimenti
        """
        try:
            # Verifica che il nome del profilo non sia vuoto
            if not profile_name or profile_name.strip() == "":
                logger.error("❌ Il nome del profilo non può essere vuoto")
                return False

            # Rimuovi il nome del profilo dalla config per evitare duplicazioni
            config_copy = config.copy()
            if "profile_name" in config_copy:
                del config_copy["profile_name"]

            # Salva il profilo
            self.profiles[profile_name] = config_copy
            result = self._save_profiles()

            if result:
                logger.info(f"✅ Profilo '{profile_name}' salvato con successo")

            return result
        except Exception as e:
            logger.error(f"❌ Errore nel salvataggio del profilo '{profile_name}': {e}")
            return False

    def delete_profile(self, profile_name: str) -> bool:
        """
        Elimina un profilo esistente.

        Args:
            profile_name (str): Nome del profilo da eliminare

        Returns:
            bool: True se l'operazione è riuscita, False altrimenti
        """
        if profile_name in self.profiles:
            try:
                del self.profiles[profile_name]
                result = self._save_profiles()

                if result:
                    logger.info(f"✅ Profilo '{profile_name}' eliminato con successo")

                return result
            except Exception as e:
                logger.error(f"❌ Errore nell'eliminazione del profilo '{profile_name}': {e}")
                return False
        else:
            logger.warning(f"⚠️ Profilo '{profile_name}' non trovato")
            return False

    def rename_profile(self, old_name: str, new_name: str) -> bool:
        """
        Rinomina un profilo esistente.

        Args:
            old_name (str): Nome attuale del profilo
            new_name (str): Nuovo nome del profilo

        Returns:
            bool: True se l'operazione è riuscita, False altrimenti
        """
        if old_name in self.profiles:
            if new_name and new_name.strip() != "" and new_name != old_name:
                try:
                    # Copia il profilo con il nuovo nome
                    self.profiles[new_name] = self.profiles[old_name]
                    # Elimina il vecchio profilo
                    del self.profiles[old_name]
                    result = self._save_profiles()

                    if result:
                        logger.info(f"✅ Profilo rinominato da '{old_name}' a '{new_name}'")

                    return result
                except Exception as e:
                    logger.error(f"❌ Errore nel rinominare il profilo da '{old_name}' a '{new_name}': {e}")
                    return False
            else:
                logger.warning("⚠️ Il nuovo nome non è valido")
                return False
        else:
            logger.warning(f"⚠️ Profilo '{old_name}' non trovato")
            return False
