"""
Gestore per diversi modelli LLM (OpenAI, Claude, DeepSeek, Baidu ERNIE).
Fornisce un'interfaccia unificata per generare query SQL.
"""
import httpx  # type: ignore
import logging
from abc import ABC, abstractmethod
from openai import OpenAI  # type: ignore
from anthropic import Anthropic  # type: ignore
# Nota: DeepSeek non ha una libreria Python ufficiale, usiamo httpx per le chiamate API
# import ernie  # Importa la libreria per Baidu ERNIE

# Configura il logging
logger = logging.getLogger(__name__)


class BaseLLM(ABC):
    """Classe base astratta per tutti i provider LLM."""

    @abstractmethod
    def generate_query(self, prompt, max_tokens=1000):
        """
        Genera una query SQL basata sul prompt fornito.

        Args:
            prompt (str): Il prompt in linguaggio naturale
            max_tokens (int): Numero massimo di token nella risposta

        Returns:
            str: La query SQL generata
        """
        pass

    @abstractmethod
    def generate_analysis(self, prompt, max_tokens=1000):
        """
        Genera un'analisi dei dati basata sul prompt fornito.

        Args:
            prompt (str): Il prompt che descrive i dati da analizzare
            max_tokens (int): Numero massimo di token nella risposta

        Returns:
            str: L'analisi generata
        """
        pass


class OpenAILLM(BaseLLM):
    """Implementazione LLM per OpenAI."""

    def __init__(self, api_key, model="gpt-4o-mini"):
        """
        Inizializza il client OpenAI.

        Args:
            api_key (str): Chiave API OpenAI
            model (str): Nome del modello da utilizzare
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate_query(self, prompt, max_tokens=1000):
        """Genera una query SQL usando OpenAI."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Sei un assistente SQL esperto."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"❌ Errore OpenAI durante la generazione della query: {e}")
            raise Exception(f"Errore OpenAI: {str(e)}")

    def generate_analysis(self, prompt, max_tokens=1000):
        """Genera un'analisi dei dati usando OpenAI."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Sei un esperto di analisi dati."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"❌ Errore OpenAI durante la generazione dell'analisi: {e}")
            raise Exception(f"Errore OpenAI: {str(e)}")


class ClaudeLLM(BaseLLM):
    """Implementazione LLM per Anthropic Claude."""

    def __init__(self, api_key, model="claude-3-haiku-20240307"):
        """
        Inizializza il client Claude.

        Args:
            api_key (str): Chiave API Anthropic
            model (str): Nome del modello da utilizzare
        """
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def generate_query(self, prompt, max_tokens=1000):
        """Genera una query SQL usando Claude."""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system="Sei un assistente SQL esperto. Genera SOLO la query SQL corretta senza spiegazioni aggiuntive.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"❌ Errore Claude durante la generazione della query: {e}")
            raise Exception(f"Errore Claude: {str(e)}")

    def generate_analysis(self, prompt, max_tokens=1000):
        """Genera un'analisi dei dati usando Claude."""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system="Sei un esperto di analisi dati.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"❌ Errore Claude durante la generazione dell'analisi: {e}")
            raise Exception(f"Errore Claude: {str(e)}")


class DeepSeekLLM(BaseLLM):
    """Implementazione LLM per DeepSeek usando l'API REST."""

    def __init__(self, api_key, model="deepseek-chat"):
        """
        Inizializza il client DeepSeek.

        Args:
            api_key (str): Chiave API DeepSeek
            model (str): Nome del modello da utilizzare
        """
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.deepseek.com/v1/chat/completions"  # Endpoint API (da verificare)

    def _make_request(self, messages, max_tokens=1000, temperature=0.7):
        """Effettua una richiesta all'API DeepSeek."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "top_p": 0.1,        # Filtra solo le opzioni più probabili
            "frequency_penalty": 0.5,  # Riduce ripetizioni (utile per dati tecnici),
            "temperature": temperature
        }

        try:
            response = httpx.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=60.0
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"❌ Errore nella richiesta DeepSeek: {response.text}")
                raise Exception(f"Errore nella richiesta DeepSeek: {response.text}")
        except Exception as e:
            logger.error(f"❌ Errore nella richiesta DeepSeek: {e}")
            raise Exception(f"Errore nella richiesta DeepSeek: {str(e)}")

    def generate_query(self, prompt, max_tokens=1000):
        """Genera una query SQL usando DeepSeek."""
        try:
            messages = [
                {"role": "system", "content": "Sei un assistente SQL esperto."},
                {"role": "user", "content": prompt}
            ]

            response = self._make_request(messages, max_tokens, 0.3)

            # Estrai il testo dalla risposta (struttura da adattare in base all'API reale)
            return response.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"❌ Errore DeepSeek durante la generazione della query: {e}")
            raise Exception(f"Errore DeepSeek: {str(e)}")

    def generate_analysis(self, prompt, max_tokens=1000):
        """Genera un'analisi dei dati usando DeepSeek."""
        try:
            messages = [
                {"role": "system", "content": "Sei un esperto di analisi dati."},
                {"role": "user", "content": prompt}
            ]

            response = self._make_request(messages, max_tokens)

            # Estrai il testo dalla risposta (struttura da adattare in base all'API reale)
            return response.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"❌ Errore DeepSeek durante la generazione della analisi: {e}")
            raise Exception(f"Errore DeepSeek: {str(e)}")


class ErnieLLM(BaseLLM):
    """Implementazione LLM per Baidu ERNIE."""

    def __init__(self, api_key, secret_key, model="ernie-bot-4"):
        """
        Inizializza il client ERNIE.

        Args:
            api_key (str): Chiave API Baidu
            secret_key (str): Chiave segreta Baidu
            model (str): Nome del modello da utilizzare
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.model = model
        self.api_url = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions"
        self.access_token = self._get_access_token()

    def _get_access_token(self):
        """Ottiene un token di accesso valido da Baidu."""
        url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={self.api_key}&client_secret={self.secret_key}"  # noqa: E501

        try:
            response = httpx.post(url)
            if response.status_code == 200:
                return response.json().get("access_token")
            else:
                logger.error(f"❌ Errore nel recupero del token Baidu: {response.text}")
                raise Exception(f"Errore nel recupero del token Baidu: {response.text}")
        except Exception as e:
            logger.error(f"❌ Errore nella richiesta del token Baidu: {e}")
            raise Exception(f"Errore nella richiesta del token Baidu: {str(e)}")

    def _make_request(self, messages):
        """Effettua una richiesta all'API ERNIE."""
        headers = {
            "Content-Type": "application/json"
        }

        params = {
            "access_token": self.access_token
        }

        payload = {
            "messages": messages,
            "model": self.model
        }

        try:
            response = httpx.post(
                self.api_url,
                headers=headers,
                params=params,
                json=payload
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"❌ Errore nella richiesta ERNIE: {response.text}")
                raise Exception(f"Errore nella richiesta ERNIE: {response.text}")
        except Exception as e:
            logger.error(f"❌ Errore nella richiesta ERNIE: {e}")
            raise Exception(f"Errore nella richiesta ERNIE: {str(e)}")

    def generate_query(self, prompt, max_tokens=1000):
        """Genera una query SQL usando ERNIE."""
        try:
            messages = [
                {"role": "system", "content": "Sei un assistente SQL esperto."},
                {"role": "user", "content": prompt}
            ]

            response = self._make_request(messages)
            return response.get("result", "")
        except Exception as e:
            logger.error(f"❌ Errore ERNIE durante la generazione della query: {e}")
            raise Exception(f"Errore ERNIE: {str(e)}")

    def generate_analysis(self, prompt, max_tokens=1000):
        """Genera un'analisi dei dati usando ERNIE."""
        try:
            messages = [
                {"role": "system", "content": "Sei un esperto di analisi dati."},
                {"role": "user", "content": prompt}
            ]

            response = self._make_request(messages)
            return response.get("result", "")
        except Exception as e:
            logger.error(f"❌ Errore ERNIE durante la generazione dell'analisi: {e}")
            raise Exception(f"Errore ERNIE: {str(e)}")


def get_llm_instance(provider, config):
    """
    Factory per creare l'istanza LLM appropriata in base al provider.

    Args:
        provider (str): Il provider LLM (openai, claude, deepseek, ernie)
        config (dict): Configurazione per il provider

    Returns:
        BaseLLM: Un'istanza dell'implementazione LLM richiesta
    """
    if provider.lower() == "openai":
        return OpenAILLM(
            api_key=config.get("api_key"),
            model=config.get("model", "gpt-4o-mini")
        )
    elif provider.lower() == "claude":
        return ClaudeLLM(
            api_key=config.get("api_key"),
            model=config.get("model", "claude-3-haiku-20240307")
        )
    elif provider.lower() == "deepseek":
        return DeepSeekLLM(
            api_key=config.get("api_key"),
            model=config.get("model", "deepseek-chat")
        )
    elif provider.lower() == "ernie":
        return ErnieLLM(
            api_key=config.get("api_key"),
            secret_key=config.get("secret_key"),
            model=config.get("model", "ernie-bot-4")
        )
    else:
        raise ValueError(f"Provider LLM non supportato: {provider}")
