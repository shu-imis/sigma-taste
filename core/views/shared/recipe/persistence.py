"""Persistence helpers for recipes and ingredients."""

from typing import Any

from django.db import transaction

from core.models import Ingredient, Recipe, User


def create_recipe_with_ingredients(
    *,
    author: User,
    payload: dict[str, Any],
    is_ai_generated: bool = False,
    source_prompt: dict[str, Any] | None = None,
) -> Recipe:
    """Persist one recipe and its ingredients in a single transaction."""
    with transaction.atomic():
        recipe = Recipe.objects.create(
            title=payload['title'],
            description=payload['description'],
            cuisine=payload['cuisine'],
            flavor=payload['flavor'],
            steps=payload['steps'],
            cooking_time=payload['cooking_time'],
            difficulty=payload['difficulty'],
            nutrition=payload.get('nutrition') or {},
            author=author,
            is_ai_generated=is_ai_generated,
            source_prompt=source_prompt or {},
        )
        ingredients = [Ingredient(recipe=recipe, **row) for row in payload['ingredients']]
        if ingredients:
            Ingredient.objects.bulk_create(ingredients)
    return recipe
