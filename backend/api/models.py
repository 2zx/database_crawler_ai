"""
Modelli Pydantic per l'API.
Definisce strutture dati robuste per validare request/response.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field  # type: ignore[import]


class SSHConfig(BaseModel):
    """Configurazione SSH per il tunnel."""
    ssh_host: str = Field(..., description="IP o hostname del server SSH")
    ssh_user: str = Field(..., description="Username per l'accesso SSH")
    ssh_key: str = Field(..., description="Chiave privata SSH")
    use_ssh: bool = Field(..., description="Se usare o meno il tunnel SSH")


class DBConfig(BaseModel):
    """Configurazione del database."""
    host: str = Field(..., description="IP o hostname del server database")
    port: str = Field(..., description="Porta del server database")
    user: str = Field(..., description="Username per l'accesso al database")
    password: str = Field(..., description="Password per l'accesso al database")
    database: str = Field(..., description="Nome del database")
    db_type: str = Field("postgresql", description="Tipo di database: postgresql o sqlserver")
    hint_category: str = Field("generale", description="Categoria di hint da utilizzare")


class LLMConfig(BaseModel):
    """Configurazione del modello di linguaggio."""
    provider: str = Field(..., description="Provider del modello: openai, claude, deepseek, gemini")
    api_key: str = Field(..., description="Chiave API del provider")
    model: Optional[str] = Field(None, description="Nome del modello specifico da utilizzare")
    secret_key: Optional[str] = Field(None, description="Chiave segreta (per alcuni provider)")


class QueryRequest(BaseModel):
    """Richiesta di esecuzione di una query in linguaggio naturale."""
    domanda: str = Field(..., description="Domanda in linguaggio naturale")
    llm_config: LLMConfig = Field(..., description="Configurazione del modello LLM")
    ssh_config: SSHConfig = Field(..., description="Configurazione SSH (anche se non usata)")
    db_config: DBConfig = Field(..., description="Configurazione del database")
    force_no_cache: bool = Field(False, description="Forza la rigenerazione ignorando la cache")


class RefreshRequest(BaseModel):
    """Richiesta di aggiornamento dello schema del database."""
    ssh_config: SSHConfig
    db_config: DBConfig


class HintRequest(BaseModel):
    """Richiesta di aggiunta di un hint."""
    hint_text: str = Field(..., description="Testo dell'hint")
    hint_category: str = Field("generale", description="Categoria dell'hint")


class HintUpdateRequest(BaseModel):
    """Richiesta di aggiornamento di un hint."""
    hint_text: Optional[str] = Field(None, description="Nuovo testo dell'hint")
    hint_category: Optional[str] = Field(None, description="Nuova categoria dell'hint")
    active: Optional[int] = Field(None, description="Nuovo stato dell'hint (1=attivo, 0=disattivo)")


class CategoryRequest(BaseModel):
    """Richiesta di aggiunta di una categoria."""
    name: str = Field(..., description="Nome della categoria")


class CategoryDeleteRequest(BaseModel):
    """Richiesta di eliminazione di una categoria."""
    name: str = Field(..., description="Nome della categoria da eliminare")
    replace_with: str = Field("generale", description="Nome della categoria con cui sostituire")


class ConnectionTestRequest(BaseModel):
    """Richiesta di test della connessione."""
    ssh_config: SSHConfig
    db_config: DBConfig


class QueryProgress(BaseModel):
    """Stato di avanzamento di una query."""
    status: str
    progress: int
    message: str
    step: str
    domanda: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_traceback: Optional[str] = None
    cache_used: Optional[bool] = None
    attempts: Optional[int] = None


class AvailableModel(BaseModel):
    """Informazioni su un modello disponibile."""
    id: str = Field(..., description="ID univoco del modello")
    name: str = Field(..., description="Nome visualizzato del modello")
    description: str = Field(..., description="Descrizione del modello")


class AvailableModelsResponse(BaseModel):
    """Risposta con l'elenco dei modelli disponibili per provider."""
    openai: List[AvailableModel]
    claude: List[AvailableModel]
    deepseek: List[AvailableModel]
    gemini: List[AvailableModel]


# Nuovi modelli per le valutazioni
class RatingRequest(BaseModel):
    """Richiesta di invio di una valutazione."""
    query_id: str = Field(..., description="ID della query")
    domanda: str = Field(..., description="Domanda originale")
    query_sql: str = Field(..., description="Query SQL eseguita")
    positive: bool = Field(..., description="Se la valutazione è positiva")
    feedback: Optional[str] = Field(None, description="Feedback testuale dell'utente")
    llm_provider: Optional[str] = Field(None, description="Provider LLM utilizzato")


class AnalysisResultRequest(BaseModel):
    """Richiesta di salvataggio di un risultato di analisi."""
    query_id: str = Field(..., description="ID della query")
    domanda: str = Field(..., description="Domanda originale")
    query_sql: str = Field(..., description="Query SQL eseguita")
    descrizione: Optional[str] = Field(None, description="Descrizione testuale dei risultati")
    dati: Optional[List[Dict[str, Any]]] = Field(None, description="Dati risultanti dall'analisi")
    grafico_path: Optional[str] = Field(None, description="Percorso del grafico generato")
    llm_provider: Optional[str] = Field(None, description="Provider LLM utilizzato")
    cache_used: bool = Field(False, description="Se è stata usata la cache")
    execution_time: Optional[int] = Field(None, description="Tempo di esecuzione in ms")
