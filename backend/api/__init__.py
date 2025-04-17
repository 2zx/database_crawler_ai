"""
Inizializzazione del package API.
"""
from fastapi import APIRouter  # type: ignore
from backend.api.query_endpoints import router as query_router
from backend.api.hint_endpoints import router as hint_router
from backend.api.schema_endpoints import router as schema_router
from backend.api.rating_endpoints import router as rating_router

# Aggregatore di tutti i router
router = APIRouter()
router.include_router(query_router)
router.include_router(hint_router)
router.include_router(schema_router)
router.include_router(rating_router)
