"""Normalization helpers for recipe payload persistence."""

from typing import Any

from core.services.recipe import (
    DEFAULT_COOKING_TIME,
    DEFAULT_CUISINE,
    DEFAULT_DIFFICULTY,
    DEFAULT_RECIPE_TITLE,
    normalize_recipe_payload,
)


def finalize_recipe_payload(
    recipe_payload: dict[str, Any],
    fallback_steps: list[str],
    fallback_ingredients: list[dict[str, str]],
) -> dict[str, Any]:
    """Finalize payload fields so save-time schema is always valid."""
    return normalize_recipe_payload(
        recipe_payload,
        defaults={
            'title': DEFAULT_RECIPE_TITLE,
            'description': '',
            'cuisine': DEFAULT_CUISINE,
            'flavor': '',
            'difficulty': DEFAULT_DIFFICULTY,
            'cooking_time': DEFAULT_COOKING_TIME,
            'nutrition': {},
        },
        fallback_steps=fallback_steps,
        fallback_ingredients=fallback_ingredients,
    )
