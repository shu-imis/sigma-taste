"""Recipe payload normalization and schema guardrails."""

import re
from typing import Any

DEFAULT_RECIPE_TITLE = 'Untitled Recipe'
DEFAULT_AI_RECIPE_TITLE = 'AI Recipe'
DEFAULT_CUISINE = 'Home Style'
DEFAULT_DIFFICULTY = 'easy'
DEFAULT_COOKING_TIME = 20
DEFAULT_STEP = 'Prepare ingredients and cook with a standard home-style method until done.'


def normalize_difficulty(value: Any, *, default: str = DEFAULT_DIFFICULTY) -> str:
    """Map free-text difficulty labels to allowed enum values."""
    candidate = str(value or default).strip().lower()
    if candidate in {'easy', 'simple'}:
        return 'easy'
    if candidate in {'medium', 'normal'}:
        return 'medium'
    if candidate in {'hard'}:
        return 'hard'
    return default if default in _valid_difficulties() else DEFAULT_DIFFICULTY


def normalize_cooking_time(value: Any, *, default: int = DEFAULT_COOKING_TIME, minimum: int = 1, maximum: int = 240) -> int:
    """Coerce cooking time into bounded integer minutes."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(minimum, min(maximum, parsed))


def normalize_steps(steps: Any, *, fallback: list[str] | None = None) -> list[str]:
    """Normalize and guarantee at least one step."""
    if isinstance(steps, list):
        normalized = [str(step).strip() for step in steps if str(step).strip()]
    else:
        normalized = []
    if normalized:
        return normalized

    fallback_values = [str(step).strip() for step in (fallback or []) if str(step).strip()]
    if fallback_values:
        return fallback_values
    return [DEFAULT_STEP]


def _model_field_max_length(model_name: str, field_name: str) -> int:
    """Read a model field's max_length lazily (a top-level models import would be circular)."""
    from core import models as core_models
    return getattr(core_models, model_name)._meta.get_field(field_name).max_length


def _valid_difficulties() -> set[str]:
    """Read allowed difficulty enum values from the Recipe model (lazy import avoids a circular dependency)."""
    from core import models as core_models
    return {value for value, _label in core_models.Recipe.DIFFICULTY_CHOICES}


def clamp_recipe_title(title: str) -> str:
    """Truncate a recipe title to the Recipe model's max_length."""
    return title[: _model_field_max_length('Recipe', 'title')]


def clamp_ingredient_row(row: dict[str, str]) -> dict[str, str]:
    """Truncate ingredient row fields to the Ingredient model's max_lengths."""
    return {
        'name': row['name'][: _model_field_max_length('Ingredient', 'name')],
        'quantity': row['quantity'][: _model_field_max_length('Ingredient', 'quantity')],
        'unit': row['unit'][: _model_field_max_length('Ingredient', 'unit')],
        'alternative': row['alternative'][: _model_field_max_length('Ingredient', 'alternative')],
    }


def normalize_ingredients(rows: Any, *, fallback: list[dict[str, str]] | None = None) -> list[dict[str, str]]:
    """Normalize ingredient rows into stable object structure."""
    normalized_rows: list[dict[str, str]] = []
    for row in rows or []:
        if isinstance(row, str):
            name = row.strip()
            if not name:
                continue
            normalized_rows.append({'name': name, 'quantity': '', 'unit': '', 'alternative': ''})
            continue
        if not isinstance(row, dict):
            continue

        name = str(row.get('name', '')).strip()
        if not name:
            continue
        normalized_rows.append(
            {
                'name': name,
                'quantity': str(row.get('quantity', '')).strip(),
                'unit': str(row.get('unit', '')).strip(),
                'alternative': str(row.get('alternative', '')).strip(),
            }
        )

    if normalized_rows:
        return normalized_rows

    fallback_rows: list[dict[str, str]] = []
    for row in fallback or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get('name', '')).strip()
        if not name:
            continue
        fallback_rows.append(
            {
                'name': name,
                'quantity': str(row.get('quantity', '')).strip(),
                'unit': str(row.get('unit', '')).strip(),
                'alternative': str(row.get('alternative', '')).strip(),
            }
        )
    return fallback_rows


def ingredient_rows_from_names(names: Any) -> list[dict[str, str]]:
    """Build canonical ingredient rows from a list of raw ingredient names."""
    normalized_rows: list[dict[str, str]] = []
    for name in names or []:
        if name is None:
            continue
        clean_name = str(name).strip()
        if not clean_name:
            continue
        normalized_rows.append({'name': clean_name, 'quantity': '', 'unit': '', 'alternative': ''})
    return normalized_rows


def normalize_flavor_tags(value: Any) -> list[str]:
    """Normalize flavor payload into an ordered, deduplicated tag list."""
    if isinstance(value, (list, tuple, set)):
        candidates = [str(item) for item in value]
    else:
        raw = str(value or '').strip()
        if not raw:
            return []
        candidates = re.split(r'[,，;/|·]+', raw)

    normalized = []
    seen = set()
    for item in candidates:
        cleaned = str(item).strip().strip('"').strip("'").strip('[]').strip('"').strip("'")
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    return normalized


def normalize_flavor(value: Any) -> str:
    """Normalize flavor into a compact comma-separated text form."""
    normalized = normalize_flavor_tags(value)
    return ', '.join(normalized)


def normalize_recipe_payload(
    recipe_data: Any,
    *,
    defaults: dict[str, Any] | None = None,
    fallback_steps: list[str] | None = None,
    fallback_ingredients: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Normalize recipe payload into canonical schema used by views/services."""
    data = dict(recipe_data) if isinstance(recipe_data, dict) else {}
    base = dict(defaults) if isinstance(defaults, dict) else {}

    title = str(data.get('title') or base.get('title') or DEFAULT_RECIPE_TITLE).strip() or DEFAULT_RECIPE_TITLE
    title = clamp_recipe_title(title)
    description = str(data.get('description') or base.get('description') or '').strip()
    cuisine = str(data.get('cuisine') or base.get('cuisine') or DEFAULT_CUISINE).strip() or DEFAULT_CUISINE
    flavor = normalize_flavor(data.get('flavor', base.get('flavor', '')))

    cooking_time = normalize_cooking_time(
        data.get('cooking_time', base.get('cooking_time', DEFAULT_COOKING_TIME)),
        default=normalize_cooking_time(base.get('cooking_time', DEFAULT_COOKING_TIME)),
    )
    difficulty = normalize_difficulty(data.get('difficulty', base.get('difficulty', DEFAULT_DIFFICULTY)))

    steps = normalize_steps(
        data.get('steps'),
        fallback=fallback_steps or base.get('steps') or [DEFAULT_STEP],
    )

    ingredients = normalize_ingredients(
        data.get('ingredients'),
        fallback=fallback_ingredients or base.get('ingredients') or [],
    )
    ingredients = [clamp_ingredient_row(row) for row in ingredients]

    nutrition = data.get('nutrition')
    if not isinstance(nutrition, dict):
        nutrition = base.get('nutrition') if isinstance(base.get('nutrition'), dict) else {}

    return {
        'title': title,
        'description': description,
        'cuisine': cuisine,
        'flavor': flavor,
        'difficulty': difficulty,
        'cooking_time': cooking_time,
        'steps': steps,
        'ingredients': ingredients,
        'nutrition': nutrition,
    }


def normalize_ai_recipe_payload(recipe_data: Any, source_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Normalize AI-generated recipe JSON into stable schema fields, defaulting from the source payload."""
    payload = dict(source_payload) if isinstance(source_payload, dict) else {}
    return normalize_recipe_payload(
        recipe_data,
        defaults={
            'title': DEFAULT_AI_RECIPE_TITLE,
            'description': '',
            'cuisine': payload.get('cuisine_preference') or DEFAULT_CUISINE,
            'flavor': payload.get('flavor_preference') or '',
            'difficulty': DEFAULT_DIFFICULTY,
            'cooking_time': payload.get('cooking_time') or DEFAULT_COOKING_TIME,
            'nutrition': {},
        },
        fallback_steps=[DEFAULT_STEP],
        fallback_ingredients=ingredient_rows_from_names(payload.get('available_ingredients', [])),
    )
