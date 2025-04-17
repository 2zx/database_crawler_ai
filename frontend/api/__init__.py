"""
Moduli per la comunicazione con le API
"""
from frontend.api.backend_client import BackendClient
from frontend.api.llm_manager import LLMManager
from frontend.api.hint_manager import HintManager
from frontend.api.rating_manager import RatingManager

__all__ = ['BackendClient', 'LLMManager', 'HintManager', 'RatingManager']
