"""
Endpoint per la gestione degli hint.
"""
from fastapi import APIRouter, HTTPException  # type: ignore
from backend.api.models import HintRequest, HintUpdateRequest, CategoryRequest, CategoryDeleteRequest
from backend.db.hint_store import HintStore
from backend.utils.logging import get_logger

logger = get_logger(__name__)

# Inizializza il router
router = APIRouter(tags=["hints"])

# Inizializza il gestore degli hint
hint_store = HintStore()


@router.get("/hints")
def get_hints():
    """
    Recupera tutti gli hint.

    Returns:
        list: Lista di tutti gli hint
    """
    return hint_store.get_all_hints()


@router.get("/hints/active")
def get_hints_active(hint_category: str = ""):
    """
    Recupera solo gli hint attivi.

    Args:
        hint_category (str, optional): Categoria per filtrare gli hint

    Returns:
        list: Lista degli hint attivi
    """
    return hint_store.get_active_hints(hint_category)


@router.get("/hints/{hint_id}")
def get_hint(hint_id: int):
    """
    Recupera un hint specifico.

    Args:
        hint_id (int): ID dell'hint da recuperare

    Returns:
        dict: Dati dell'hint
    """
    hint = hint_store.get_hint_by_id(hint_id)
    if hint:
        return hint
    raise HTTPException(status_code=404, detail="Hint non trovato")


@router.post("/hints")
def create_hint(request: HintRequest):
    """
    Crea un nuovo hint.

    Args:
        request (HintRequest): Dati del nuovo hint

    Returns:
        dict: Stato dell'operazione e ID del nuovo hint
    """
    hint_id = hint_store.add_hint(request.hint_text, request.hint_category)
    if hint_id:
        return {"status": "success", "id": hint_id}
    raise HTTPException(status_code=500, detail="Errore nella creazione dell'hint")


@router.put("/hints/{hint_id}")
def modify_hint(hint_id: int, request: HintUpdateRequest):
    """
    Aggiorna un hint esistente.

    Args:
        hint_id (int): ID dell'hint da aggiornare
        request (HintUpdateRequest): Nuovi dati dell'hint

    Returns:
        dict: Stato dell'operazione
    """
    success = hint_store.update_hint(
        hint_id,
        request.hint_text,
        request.hint_category,
        request.active
    )
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Hint non trovato o errore nell'aggiornamento")


@router.delete("/hints/{hint_id}")
def remove_hint(hint_id: int):
    """
    Elimina un hint.

    Args:
        hint_id (int): ID dell'hint da eliminare

    Returns:
        dict: Stato dell'operazione
    """
    success = hint_store.delete_hint(hint_id)
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Hint non trovato o errore nell'eliminazione")


@router.put("/hints/{hint_id}/toggle")
def toggle_hint(hint_id: int):
    """
    Attiva o disattiva un hint.

    Args:
        hint_id (int): ID dell'hint da attivare/disattivare

    Returns:
        dict: Stato dell'operazione
    """
    success = hint_store.toggle_hint_status(hint_id)
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Hint non trovato o errore nel cambio di stato")


@router.get("/hints/formatted")
def get_formatted_hints(category: str = None):
    """
    Recupera gli hint formattati per il prompt.

    Args:
        category (str, optional): Categoria da filtrare

    Returns:
        dict: Hint formattati per il prompt
    """
    formatted = hint_store.format_hints_for_prompt(category)
    return {"hints_formatted": formatted}


@router.post("/hints/export")
def export_hints():
    """
    Esporta gli hint in un file JSON.

    Returns:
        dict: Stato dell'operazione
    """
    success = hint_store.export_hints_to_json()
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Errore nell'esportazione degli hint")


@router.post("/hints/import")
def import_hints():
    """
    Importa gli hint da un file JSON.

    Returns:
        dict: Stato dell'operazione
    """
    success = hint_store.import_hints_from_json()
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Errore nell'importazione degli hint")


@router.get("/categories")
def get_categories():
    """
    Recupera tutte le categorie disponibili.

    Returns:
        dict: Lista delle categorie
    """
    categories = hint_store.get_all_categories()
    return {"categories": categories}


@router.post("/categories")
def create_category(request: CategoryRequest):
    """
    Crea una nuova categoria.

    Args:
        request (CategoryRequest): Dati della nuova categoria

    Returns:
        dict: Stato dell'operazione
    """
    success = hint_store.add_category(request.name)
    if success:
        return {"status": "success", "message": f"Categoria '{request.name}' creata"}
    else:
        raise HTTPException(status_code=400, detail=f"La categoria '{request.name}' esiste già")


@router.delete("/categories")
def remove_category(request: CategoryDeleteRequest):
    """
    Elimina una categoria e aggiorna gli hint associati.

    Args:
        request (CategoryDeleteRequest): Dati della categoria da eliminare

    Returns:
        dict: Stato dell'operazione
    """
    if request.name == "generale":
        raise HTTPException(status_code=400, detail="Non è possibile eliminare la categoria 'generale'")

    affected_rows = hint_store.delete_category(request.name, request.replace_with)
    if affected_rows >= 0:
        return {"status": "success", "affected_rows": affected_rows}
    else:
        raise HTTPException(status_code=500, detail="Errore nell'eliminazione della categoria")
