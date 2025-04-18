"""
Gestore per diversi modelli LLM (OpenAI, Claude, DeepSeek, Gemini).
Fornisce un'interfaccia unificata per generare query SQL.
"""
import httpx  # type: ignore
import re
from abc import ABC, abstractmethod
from openai import OpenAI  # type: ignore
from anthropic import Anthropic  # type: ignore
from backend.utils.logging import get_logger
from backend.config import DEFAULT_LLM_MODELS

# Configura il logging
logger = get_logger(__name__)


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

    @abstractmethod
    def generate_related_questions(self, context, results, max_questions=5):
        """
        Genera domande correlate basate sui risultati dell'analisi precedente.

        Args:
            context (str): Il contesto della domanda originale
            results (dict): I risultati dell'analisi precedente
            max_questions (int): Numero massimo di domande da generare

        Returns:
            list: Lista di domande correlate
        """
        pass


class OpenAILLM(BaseLLM):
    """Implementazione LLM per OpenAI."""

    def __init__(self, api_key, model=None):
        """
        Inizializza il client OpenAI.

        Args:
            api_key (str): Chiave API OpenAI
            model (str, optional): Nome del modello da utilizzare
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model or DEFAULT_LLM_MODELS["openai"]

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

    def generate_related_questions(self, context, results, max_questions=5):
        """Genera domande correlate usando OpenAI."""
        try:
            prompt = f"""
            Basandoti sulla seguente analisi di dati, genera {max_questions} domande di approfondimento
            che l'utente potrebbe voler fare successivamente.
            Le domande devono essere specifiche, correlate ai dati analizzati, e aiutare l'utente
            a esplorare ulteriormente i dati o a scoprire nuovi insights.

            {context}

            Restituisci solo un elenco di domande numerate, una per riga, senza ulteriori spiegazioni.
            Le domande devono essere formulate in italiano e in modo chiaro e conciso.
            """

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system",
                     "content": "Sei un esperto di analisi dati che suggerisce domande di approfondimento pertinenti."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7  # Un po' di creatività per generare domande diverse
            )

            result = response.choices[0].message.content.strip()

            # Elaborazione della risposta per estrarre solo le domande
            questions = []
            for line in result.split('\n'):
                # Rimuovi numerazione e altri caratteri
                line = line.strip()
                if line:
                    # Rimuovi numerazione (es. "1. ", "1) ", ecc.)
                    cleaned_line = re.sub(r'^\d+[\.\)\-]\s*', '', line)
                    if cleaned_line:
                        questions.append(cleaned_line)

            # Limita al numero massimo richiesto
            return questions[:max_questions]

        except Exception as e:
            logger.error(f"❌ Errore OpenAI durante la generazione delle domande correlate: {e}")
            return []


class ClaudeLLM(BaseLLM):
    """Implementazione LLM per Anthropic Claude."""

    def __init__(self, api_key, model=None):
        """
        Inizializza il client Claude.

        Args:
            api_key (str): Chiave API Anthropic
            model (str, optional): Nome del modello da utilizzare
        """
        self.client = Anthropic(api_key=api_key)
        self.model = model or DEFAULT_LLM_MODELS["claude"]

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

    def generate_related_questions(self, context, results, max_questions=3):
        """Genera domande correlate usando Claude."""
        try:
            prompt = f"""
            Basandoti sulla seguente analisi di dati, genera {max_questions} domande di approfondimento
            che l'utente potrebbe voler fare successivamente.
            Le domande devono essere specifiche, correlate ai dati analizzati, e aiutare l'utente
            a esplorare ulteriormente i dati o a scoprire nuovi insights.

            {context}

            Restituisci solo un elenco di domande numerate, una per riga, senza ulteriori spiegazioni.
            Le domande devono essere formulate in italiano e in modo chiaro e conciso.
            """

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.7,
                system="Sei un esperto di analisi dati che suggerisce domande di approfondimento pertinenti.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            result = response.content[0].text.strip()

            # Elaborazione della risposta per estrarre solo le domande
            questions = []
            for line in result.split('\n'):
                # Rimuovi numerazione e altri caratteri
                line = line.strip()
                if line:
                    # Rimuovi numerazione (es. "1. ", "1) ", ecc.)
                    cleaned_line = re.sub(r'^\d+[\.\)\-]\s*', '', line)
                    if cleaned_line:
                        questions.append(cleaned_line)

            # Limita al numero massimo richiesto
            return questions[:max_questions]

        except Exception as e:
            logger.error(f"❌ Errore Claude durante la generazione delle domande correlate: {e}")
            return []


class DeepSeekLLM(BaseLLM):
    """Implementazione LLM per DeepSeek usando l'API REST."""

    def __init__(self, api_key, model=None):
        """
        Inizializza il client DeepSeek.

        Args:
            api_key (str): Chiave API DeepSeek
            model (str, optional): Nome del modello da utilizzare
        """
        self.api_key = api_key
        self.model = model or DEFAULT_LLM_MODELS["deepseek"]
        self.api_url = "https://api.deepseek.com/v1/chat/completions"  # Endpoint API

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

            # Estrai il testo dalla risposta
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

            # Estrai il testo dalla risposta
            return response.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"❌ Errore DeepSeek durante la generazione della analisi: {e}")
            raise Exception(f"Errore DeepSeek: {str(e)}")

    def generate_related_questions(self, context, results, max_questions=3):
        """Genera domande correlate usando DeepSeek."""
        try:
            prompt = f"""
            Basandoti sulla seguente analisi di dati, genera {max_questions} domande di approfondimento
            che l'utente potrebbe voler fare successivamente.
            Le domande devono essere specifiche, correlate ai dati analizzati, e aiutare l'utente
            a esplorare ulteriormente i dati o a scoprire nuovi insights.

            {context}

            Restituisci solo un elenco di domande numerate, una per riga, senza ulteriori spiegazioni.
            Le domande devono essere formulate in italiano e in modo chiaro e conciso.
            """

            messages = [
                {"role": "system",
                 "content": "Sei un esperto di analisi dati che suggerisce domande di approfondimento pertinenti."},
                {"role": "user", "content": prompt}
            ]

            response = self._make_request(messages, 1000, 0.7)

            # Estrai il testo dalla risposta
            result = response.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

            # Elaborazione della risposta per estrarre solo le domande
            questions = []
            for line in result.split('\n'):
                # Rimuovi numerazione e altri caratteri
                line = line.strip()
                if line:
                    # Rimuovi numerazione (es. "1. ", "1) ", ecc.)
                    cleaned_line = re.sub(r'^\d+[\.\)\-]\s*', '', line)
                    if cleaned_line:
                        questions.append(cleaned_line)

            # Limita al numero massimo richiesto
            return questions[:max_questions]

        except Exception as e:
            logger.error(f"❌ Errore DeepSeek durante la generazione delle domande correlate: {e}")
            return []


class GeminiLLM(BaseLLM):
    """Implementazione LLM per Google Gemini usando l'API REST con formato chat."""

    def __init__(self, api_key, model=None):
        """
        Inizializza il client Gemini.

        Args:
            api_key (str): Chiave API Google Gemini
            model (str, optional): Nome del modello da utilizzare
        """
        self.api_key = api_key
        self.model = model or DEFAULT_LLM_MODELS["gemini"]
        # Utilizziamo l'endpoint chat per mantenere il contesto
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        self.chat_history = []
        logger.info(f"Inizializzato Gemini LLM con model={self.model} e supporto chat")

    def _make_chat_request(self, messages, max_tokens=1000, temperature=0.7):
        """
        Effettua una richiesta all'API Gemini utilizzando il formato chat.

        Args:
            messages (list): Lista di messaggi nel formato [{"role": "...", "content": "..."}]
            max_tokens (int): Numero massimo di token da generare
            temperature (float): Temperatura per la generazione
        """
        headers = {
            "Content-Type": "application/json"
        }

        # Parametri della query string
        params = {
            "key": self.api_key
        }

        # Converti i messaggi nel formato richiesto da Gemini
        contents = []
        for msg in messages:
            role = "user" if msg["role"] in ["user", "system"] else "model"
            content = msg["content"]

            # Aggiungi un prefisso per distinguere le istruzioni di sistema
            if msg["role"] == "system":
                content = f"[Istruzione di sistema] {content}"

            contents.append({
                "role": role,
                "parts": [{"text": content}]
            })

        # Prepara il corpo della richiesta
        payload = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
                "topP": 0.8,
                "topK": 40
            }
        }

        try:
            logger.info(f"Invio richiesta chat a {self.api_url} con {len(contents)} messaggi")
            response = httpx.post(
                self.api_url,
                headers=headers,
                params=params,
                json=payload,
                timeout=60.0
            )

            if response.status_code == 200:
                return response.json()
            else:
                error_message = f"Errore nella richiesta Gemini: HTTP {response.status_code} - {response.text}"
                logger.error(error_message)
                raise Exception(error_message)
        except Exception as e:
            logger.error(f"❌ Errore nella richiesta Gemini: {e}")
            raise Exception(f"Errore nella richiesta Gemini: {str(e)}")

    def _extract_text_from_response(self, response):
        """Estrae il testo dalla risposta di Gemini."""
        try:
            # Verifica che la risposta contenga candidati
            if "candidates" not in response or not response["candidates"]:
                logger.warning("Risposta Gemini senza candidati")
                return ""

            # Ottieni il contenuto dal primo candidato
            content = response["candidates"][0].get("content", {})

            # Estrai il testo da tutte le parti
            result = ""
            if "parts" in content:
                for part in content["parts"]:
                    if "text" in part:
                        result += part["text"]

            return result.strip()
        except Exception as e:
            logger.error(f"Errore nell'estrazione del testo dalla risposta: {e}")
            return ""

    def _update_chat_history(self, role, content, response=None):
        """
        Aggiorna la cronologia della chat con un nuovo messaggio e una risposta.

        Args:
            role (str): Il ruolo del messaggio ('user' o 'system')
            content (str): Il contenuto del messaggio
            response (str, optional): La risposta dell'assistente se presente
        """
        # Aggiungi il messaggio dell'utente alla cronologia
        self.chat_history.append({"role": role, "content": content})

        # Se è presente una risposta, aggiungila alla cronologia
        if response:
            self.chat_history.append({"role": "assistant", "content": response})

        # Limita la cronologia alle ultime 10 interazioni per evitare di superare il limite di token
        if len(self.chat_history) > 20:
            self.chat_history = self.chat_history[-20:]

    def generate_query(self, prompt, max_tokens=1000):
        """Genera una query SQL usando Gemini mantenendo il contesto della conversazione."""
        try:
            # Prepara i messaggi per la chat
            messages = [
                {"role": "system",
                 "content": "Sei un assistente SQL esperto. Genera SOLO la query SQL corretta senza spiegazioni aggiuntive."}
            ]

            # Aggiungi la cronologia della chat (senza i messaggi di sistema)
            for msg in self.chat_history:
                if msg["role"] != "system":
                    messages.append(msg)

            # Aggiungi il prompt corrente
            messages.append({"role": "user", "content": prompt})

            # Effettua la richiesta chat
            response = self._make_chat_request(
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.3
            )

            # Estrai il testo
            result = self._extract_text_from_response(response)

            # Aggiorna la cronologia della chat
            self._update_chat_history("user", prompt, result)

            return result
        except Exception as e:
            logger.error(f"❌ Errore Gemini durante la generazione della query: {e}")
            raise Exception(f"Errore Gemini: {str(e)}")

    def generate_analysis(self, prompt, max_tokens=1000):
        """Genera un'analisi dei dati usando Gemini mantenendo il contesto della conversazione."""
        try:
            # Prepara i messaggi per la chat
            messages = [
                {"role": "system", "content": "Sei un esperto di analisi dati."}
            ]

            # Aggiungi la cronologia della chat (senza i messaggi di sistema)
            for msg in self.chat_history:
                if msg["role"] != "system":
                    messages.append(msg)

            # Aggiungi il prompt corrente
            messages.append({"role": "user", "content": prompt})

            # Effettua la richiesta chat
            response = self._make_chat_request(
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7
            )

            # Estrai il testo
            result = self._extract_text_from_response(response)

            # Aggiorna la cronologia della chat
            self._update_chat_history("user", prompt, result)

            return result
        except Exception as e:
            logger.error(f"❌ Errore Gemini durante la generazione dell'analisi: {e}")
            raise Exception(f"Errore Gemini: {str(e)}")

    def generate_related_questions(self, context, results, max_questions=3):
        """Genera domande correlate usando Gemini."""
        try:
            prompt = f"""
            Basandoti sulla seguente analisi di dati, genera {max_questions} domande di approfondimento
            che l'utente potrebbe voler fare successivamente.
            Le domande devono essere specifiche, correlate ai dati analizzati, e aiutare l'utente
            a esplorare ulteriormente i dati o a scoprire nuovi insights.

            {context}

            Restituisci solo un elenco di domande numerate, una per riga, senza ulteriori spiegazioni.
            Le domande devono essere formulate in italiano e in modo chiaro e conciso.
            """

            # Prepara i messaggi per la chat
            messages = [
                {"role": "system",
                 "content": "Sei un esperto di analisi dati che suggerisce domande di approfondimento pertinenti."},
                {"role": "user", "content": prompt}
            ]

            # Effettua la richiesta chat (senza aggiungere alla cronologia per non inquinare il contesto)
            response = self._make_chat_request(
                messages=messages,
                max_tokens=1000,
                temperature=0.7
            )

            # Estrai il testo dalla risposta
            result = self._extract_text_from_response(response)

            # Elaborazione della risposta per estrarre solo le domande
            questions = []
            for line in result.split('\n'):
                # Rimuovi numerazione e altri caratteri
                line = line.strip()
                if line:
                    # Rimuovi numerazione (es. "1. ", "1) ", ecc.)
                    cleaned_line = re.sub(r'^\d+[\.\)\-]\s*', '', line)
                    if cleaned_line:
                        questions.append(cleaned_line)

            # Limita al numero massimo richiesto
            return questions[:max_questions]

        except Exception as e:
            logger.error(f"❌ Errore Gemini durante la generazione delle domande correlate: {e}")
            return []

    def clear_chat_history(self):
        """Resetta la cronologia della chat."""
        self.chat_history = []
        logger.info("Cronologia chat resettata")


def get_llm_instance(provider, config):
    """
    Factory per creare l'istanza LLM appropriata in base al provider.

    Args:
        provider (str): Il provider LLM (openai, claude, deepseek, gemini)
        config (dict): Configurazione per il provider

    Returns:
        BaseLLM: Un'istanza dell'implementazione LLM richiesta
    """
    if provider.lower() == "openai":
        return OpenAILLM(
            api_key=config.get("api_key"),
            model=config.get("model")
        )
    elif provider.lower() == "claude":
        return ClaudeLLM(
            api_key=config.get("api_key"),
            model=config.get("model")
        )
    elif provider.lower() == "deepseek":
        return DeepSeekLLM(
            api_key=config.get("api_key"),
            model=config.get("model")
        )
    elif provider.lower() == "gemini":
        return GeminiLLM(
            api_key=config.get("api_key"),
            model=config.get("model")
        )
    else:
        raise ValueError(f"Provider LLM non supportato: {provider}")
