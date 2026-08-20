"""Ollama integration for model discovery and recipe generation."""

import json
import re
from collections.abc import Callable
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache

from core.text_utils import contains_cjk

from ..recipe.schema import normalize_ai_recipe_payload


class OllamaError(Exception):
    """Raised when Ollama generation fails."""


MODEL_LIST_CACHE_KEY = 'ollama:available_models:v1'
SELECTED_MODEL_SESSION_KEY = 'ai:selected_model:v1'


def _clean_model_name(value: str | None) -> str:
    """Normalize model identifiers from user input/cache/config."""
    return str(value or '').strip()


def get_session_selected_model(request) -> str:
    """Read the user's currently remembered local model from session."""
    session = getattr(request, 'session', None)
    if session is None:
        return ''
    return _clean_model_name(session.get(SELECTED_MODEL_SESSION_KEY, ''))


def store_session_selected_model(request, selected_model: str | None) -> None:
    """Persist or clear the user's currently selected local model in session."""
    session = getattr(request, 'session', None)
    if session is None:
        return

    normalized = _clean_model_name(selected_model)
    if normalized:
        session[SELECTED_MODEL_SESSION_KEY] = normalized
    else:
        session.pop(SELECTED_MODEL_SESSION_KEY, None)
    session.modified = True


def _normalize_output_language(language: str | None) -> str:
    """Normalize user language input to supported internal values."""
    value = str(language or '').strip().lower()
    if value.startswith('zh'):
        return 'zh'
    return 'en'


def _extract_json(text: str) -> dict[str, Any]:
    """Extract and parse JSON object from model output text."""
    if not text:
        raise OllamaError('The model returned no content.')

    text = text.strip()
    fenced = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    else:
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        if not text.startswith('{'):
            match = re.search(r'(\{.*\})', text, re.DOTALL)
            if match:
                text = match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise OllamaError(f'The model output could not be parsed as JSON: {exc}') from exc


def _build_prompt(payload: dict[str, Any], output_language: str = 'en') -> str:
    """Build recipe generation prompt with strict JSON contract."""
    ingredients = ', '.join(payload.get('available_ingredients', []))
    cooking_time = payload.get('cooking_time')
    flavor_preference = payload.get('flavor_preference') or 'No preference'
    cuisine_preference = payload.get('cuisine_preference') or 'No preference'
    health_goal = payload.get('health_goal') or 'Balanced'
    allergies = payload.get('allergies') or 'None listed'
    language = _normalize_output_language(output_language)
    if language == 'zh':
        language_requirements = (
            '- Output language: Simplified Chinese.\n'
            '- Keep "difficulty" value in English enum only: easy|medium|hard.'
        )
    else:
        language_requirements = (
            '- Output language: English only.\n'
            '- Never output Chinese characters in title, description, cuisine, flavor, ingredients, steps, or nutrition fields.\n'
            '- If any provided ingredient is non-English, translate it into natural kitchen English.'
        )

    return f"""
You are an experienced home-cooking recipe designer.
Create one practical, structured recipe based on:
- Available ingredients: {ingredients}
- Target cooking time (minutes): {cooking_time}
- Flavor preference: {flavor_preference}
- Cuisine preference: {cuisine_preference}
- Health goal: {health_goal}
- Allergies to avoid: {allergies}
- Never include ingredients that conflict with the listed allergies.
{language_requirements}

Return strict JSON only. Do not include extra text.
JSON must match this schema:
{{
  "title": "Recipe name",
  "description": "One-line summary",
  "cuisine": "Cuisine",
  "flavor": "Flavor tags",
  "cooking_time": 20,
  "difficulty": "easy|medium|hard",
  "ingredients": [
    {{"name": "Ingredient", "quantity": "200", "unit": "g", "alternative": ""}}
  ],
  "steps": ["Step 1", "Step 2"],
  "nutrition": {{
    "calories": "Approx. 420 kcal",
    "protein": "Approx. 24 g"
  }}
}}
""".strip()


def _build_language_repair_prompt(recipe_data: dict[str, Any], output_language: str = 'en') -> str:
    """Build translation-only prompt to repair language consistency."""
    language = _normalize_output_language(output_language)
    language_label = 'Simplified Chinese' if language == 'zh' else 'English'
    return f"""
Rewrite the recipe JSON below so all user-facing text is in {language_label}.
Keep the exact JSON structure and keep all numeric values unchanged.
Keep "difficulty" in English enum only: easy|medium|hard.
Return strict JSON only.
Input JSON:
{json.dumps(recipe_data, ensure_ascii=False)}
""".strip()


def _configured_model_fallbacks() -> list[str]:
    """Read configured model candidates in deterministic order."""
    models: list[str] = []
    configured = [
        getattr(settings, 'OLLAMA_DEFAULT_MODEL', ''),
        *getattr(settings, 'OLLAMA_MODEL_CANDIDATES', []),
    ]
    for item in configured:
        model = _clean_model_name(item)
        if model and model not in models:
            models.append(model)
    return models


def list_available_models(*, refresh: bool = False) -> list[str]:
    """List currently available Ollama models from the local Ollama service."""
    cache_ttl = max(int(getattr(settings, 'OLLAMA_MODEL_LIST_CACHE_TTL', 30)), 0)
    negative_cache_ttl = max(int(getattr(settings, 'OLLAMA_MODEL_LIST_NEGATIVE_CACHE_TTL', 5)), 0)
    if not refresh:
        cached_models = cache.get(MODEL_LIST_CACHE_KEY)
        if isinstance(cached_models, list):
            return [_clean_model_name(model) for model in cached_models if _clean_model_name(model)]

    try:
        response = requests.get(
            f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags",
            timeout=min(settings.OLLAMA_TIMEOUT, 8),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        if negative_cache_ttl > 0:
            cache.set(MODEL_LIST_CACHE_KEY, [], timeout=negative_cache_ttl)
        return []

    models: list[str] = []
    for item in payload.get('models') or []:
        model = _clean_model_name(item.get('model') or item.get('name'))
        if model and model not in models:
            models.append(model)

    if cache_ttl > 0:
        cache.set(MODEL_LIST_CACHE_KEY, models, timeout=cache_ttl)
    return models


def select_default_model(available_models: list[str]) -> str:
    """Select default model from the currently available local list."""
    clean_available: list[str] = []
    for item in available_models:
        model = _clean_model_name(item)
        if model and model not in clean_available:
            clean_available.append(model)
    return clean_available[0] if clean_available else ''


def select_session_or_default_model(request, available_models: list[str]) -> str:
    """Prefer a remembered live model, otherwise fall back to the first available one."""
    remembered_model = get_session_selected_model(request)
    if remembered_model and remembered_model in available_models:
        return remembered_model
    if remembered_model:
        store_session_selected_model(request, '')
    return select_default_model(available_models)


def resolve_model_name(
    selected_model: str | None = None,
    *,
    available_models: list[str] | None = None,
    require_listed: bool = False,
) -> str:
    """Resolve final model using explicit input, live availability, and fallback policy."""
    selected = _clean_model_name(selected_model)
    resolved_available = available_models if available_models is not None else list_available_models()
    default_live_model = select_default_model(resolved_available)

    if selected:
        if require_listed and selected not in resolved_available:
            raise OllamaError('Selected model is not currently available in local Ollama.')
        return selected

    if default_live_model:
        return default_live_model

    fallbacks = _configured_model_fallbacks()
    if fallbacks:
        return fallbacks[0]

    raise OllamaError('No available model found. Please pull a model in local Ollama and select it on the page.')


def _chat_with_ollama(resolved_model: str, messages: list[dict[str, str]]) -> str:
    """Send a chat request to Ollama and return the textual content payload."""
    request_body = {
        'model': resolved_model,
        'stream': False,
        'format': 'json',
        'messages': messages,
    }

    try:
        response = requests.post(
            f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
            json=request_body,
            timeout=settings.OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise OllamaError(f'Ollama request failed: {exc}') from exc

    try:
        model_payload = response.json()
    except ValueError as exc:
        raise OllamaError('Ollama returned a non-JSON response.') from exc

    return (model_payload.get('message') or {}).get('content', '')


def _repair_recipe_language_if_needed(
    *,
    recipe: dict[str, Any],
    payload: dict[str, Any],
    language: str,
    resolved_model: str,
    normalize_fn: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Run one best-effort language repair pass for English outputs with CJK leakage."""
    if language != 'en' or not contains_cjk(recipe):
        return recipe

    repair_messages = [
        {'role': 'system', 'content': 'You translate recipe JSON. Return strict JSON only.'},
        {'role': 'user', 'content': _build_language_repair_prompt(recipe, output_language='en')},
    ]
    try:
        repaired_content = _chat_with_ollama(resolved_model, repair_messages)
        repaired_data = _extract_json(repaired_content)
        return normalize_fn(repaired_data, payload)
    except OllamaError:
        return recipe


def generate_recipe(payload: dict[str, Any], model: str | None = None, output_language: str = 'en') -> dict[str, Any]:
    """Generate one recipe in strict JSON format from the given payload."""
    resolved_model = resolve_model_name(model)
    language = _normalize_output_language(output_language)

    base_messages = [
        {'role': 'system', 'content': 'You are a professional recipe assistant. Return strict JSON only.'},
        {'role': 'user', 'content': _build_prompt(payload, output_language=language)},
    ]
    content = _chat_with_ollama(resolved_model, base_messages)
    data = _extract_json(content)
    recipe = normalize_ai_recipe_payload(data, payload)
    return _repair_recipe_language_if_needed(
        recipe=recipe,
        payload=payload,
        language=language,
        resolved_model=resolved_model,
        normalize_fn=normalize_ai_recipe_payload,
    )
