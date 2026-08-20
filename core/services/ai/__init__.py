"""AI service helpers."""

from .ollama_client import (
    OllamaError,
    generate_recipe,
    list_available_models,
    resolve_model_name,
    select_session_or_default_model,
    store_session_selected_model,
)

__all__ = [
    'OllamaError',
    'generate_recipe',
    'list_available_models',
    'resolve_model_name',
    'select_session_or_default_model',
    'store_session_selected_model',
]
