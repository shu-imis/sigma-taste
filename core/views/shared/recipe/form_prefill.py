"""Recipe Studio prefill helpers shared across AI and manual flows."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

RECIPE_CREATE_PREFILL_SESSION_KEY = 'recipe:create:prefill:v1'


def _serialize_steps(steps: Iterable[str]) -> str:
    rendered_steps: list[str] = []
    for index, step in enumerate(steps, start=1):
        cleaned = str(step or '').strip()
        if cleaned:
            rendered_steps.append(f'{index}. {cleaned}')
    return '\n'.join(rendered_steps)


def _serialize_ingredients(ingredients: Iterable[dict[str, Any]]) -> str:
    rendered_rows: list[str] = []
    for ingredient in ingredients:
        row = ingredient if isinstance(ingredient, dict) else {}
        name = str(row.get('name') or '').strip()
        if not name:
            continue
        rendered_rows.append(
            ','.join(
                [
                    name,
                    str(row.get('quantity') or '').strip(),
                    str(row.get('unit') or '').strip(),
                    str(row.get('alternative') or '').strip(),
                ]
            )
        )
    return '\n'.join(rendered_rows)


def build_recipe_create_initial(
    recipe_payload: dict[str, Any],
    *,
    source_draft_id: str = '',
    source_draft_token: str = '',
) -> dict[str, Any]:
    """Convert a normalized recipe payload into Recipe Studio form initials."""
    payload = recipe_payload if isinstance(recipe_payload, dict) else {}
    return {
        'title': str(payload.get('title') or '').strip(),
        'description': str(payload.get('description') or '').strip(),
        'cuisine': str(payload.get('cuisine') or '').strip(),
        'flavor': str(payload.get('flavor') or '').strip(),
        'cooking_time': payload.get('cooking_time') or '',
        'difficulty': str(payload.get('difficulty') or '').strip(),
        'steps_text': _serialize_steps(payload.get('steps') or []),
        'ingredients_text': _serialize_ingredients(payload.get('ingredients') or []),
        'source_draft_id': str(source_draft_id or '').strip(),
        'source_draft_token': str(source_draft_token or '').strip(),
    }


def stash_recipe_create_prefill(request, initial: dict[str, Any]) -> None:
    """Persist one Recipe Studio prefill payload in the current session."""
    request.session[RECIPE_CREATE_PREFILL_SESSION_KEY] = dict(initial or {})
    request.session.modified = True


def read_recipe_create_prefill(request) -> dict[str, Any]:
    """Read the current Recipe Studio prefill payload without consuming it."""
    initial = request.session.get(RECIPE_CREATE_PREFILL_SESSION_KEY, {})
    return dict(initial) if isinstance(initial, dict) else {}


def clear_recipe_create_prefill(request) -> None:
    """Clear any stored Recipe Studio prefill payload from the session."""
    request.session.pop(RECIPE_CREATE_PREFILL_SESSION_KEY, None)
    request.session.modified = True
