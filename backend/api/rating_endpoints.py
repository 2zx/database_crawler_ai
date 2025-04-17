"""
Endpoint per la gestione delle valutazioni delle query.
"""
from fastapi import APIRouter, HTTPException  # type: ignore
from backend.api.models import RatingRequest, AnalysisResultRequest
from backend.db.rating_store import RatingStore
from backend.utils.logging import get_logger

logger = get_logger(__name__)

# Inizializza il router
router = APIRouter(tags=["ratings"])

# Inizializza il gestore delle valutazioni
rating_store = RatingStore()


@router.post("/ratings")
def submit_rating(request: RatingRequest):
    """
    Invia una valutazione per una query.

    Args:
        request (RatingRequest): Dati della valutazione

    Returns:
        dict: Stato dell'operazione e ID della valutazione
    """
    rating_id = rating_store.save_rating(
        query_id=request.query_id,
        domanda=request.domanda,
        query_sql=request.query_sql,
        positive=request.positive,
        feedback=request.feedback,
        llm_provider=request.llm_provider
    )

    if rating_id:
        return {"status": "success", "id": rating_id}
    raise HTTPException(status_code=500, detail="Errore nel salvataggio della valutazione")


@router.post("/analysis_results")
def save_analysis_result(request: AnalysisResultRequest):
    """
    Salva il risultato di un'analisi.

    Args:
        request (AnalysisResultRequest): Dati del risultato

    Returns:
        dict: Stato dell'operazione e ID del risultato
    """
    result_id = rating_store.save_analysis_result(
        query_id=request.query_id,
        domanda=request.domanda,
        query_sql=request.query_sql,
        descrizione=request.descrizione,
        dati=request.dati,
        grafico_path=request.grafico_path,
        llm_provider=request.llm_provider,
        cache_used=request.cache_used,
        execution_time=request.execution_time,
        error=request.error,
        error_traceback=request.error_traceback
    )

    if result_id:
        return {"status": "success", "id": result_id}
    raise HTTPException(status_code=500, detail="Errore nel salvataggio del risultato")


@router.get("/ratings/{query_id}")
def get_rating(query_id: str):
    """
    Recupera una valutazione specifica.

    Args:
        query_id (str): ID della query

    Returns:
        dict: Dati della valutazione
    """
    rating = rating_store.get_rating(query_id)
    if rating:
        return rating
    raise HTTPException(status_code=404, detail="Valutazione non trovata")


@router.get("/analysis_results/{query_id}")
def get_analysis_result(query_id: str):
    """
    Recupera un risultato di analisi specifico.

    Args:
        query_id (str): ID della query

    Returns:
        dict: Dati del risultato
    """
    result = rating_store.get_analysis_result(query_id)
    if result:
        return result
    raise HTTPException(status_code=404, detail="Risultato non trovato")


@router.get("/analysis_results")
def get_all_analysis_results(limit: int = 50, offset: int = 0):
    """
    Recupera tutti i risultati delle analisi.

    Args:
        limit (int): Limite di risultati
        offset (int): Offset per la paginazione

    Returns:
        list: Lista di risultati
    """
    return rating_store.get_all_analysis_results(limit, offset)


@router.get("/ratings/stats")
def get_ratings_stats():
    """
    Ottiene statistiche sulle valutazioni.

    Returns:
        dict: Statistiche sulle valutazioni
    """
    return rating_store.get_ratings_stats()
