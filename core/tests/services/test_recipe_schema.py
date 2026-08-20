"""Tests for recipe schema normalization helpers."""

from django.test import SimpleTestCase

from core.models import Ingredient, Recipe
from core.services.recipe import (
    DEFAULT_CUISINE,
    DEFAULT_RECIPE_TITLE,
    ingredient_rows_from_names,
    normalize_flavor,
    normalize_flavor_tags,
    normalize_recipe_payload,
)


class RecipeSchemaHelperTests(SimpleTestCase):
    """Low-level normalization helpers should stay deterministic."""

    def test_ingredient_rows_from_names_discards_empty_values(self):
        rows = ingredient_rows_from_names([' tomato ', '', None, ' basil '])
        self.assertEqual(
            rows,
            [
                {'name': 'tomato', 'quantity': '', 'unit': '', 'alternative': ''},
                {'name': 'basil', 'quantity': '', 'unit': '', 'alternative': ''},
            ],
        )

    def test_ingredient_rows_from_names_returns_empty_list_for_empty_input(self):
        self.assertEqual(ingredient_rows_from_names([]), [])
        self.assertEqual(ingredient_rows_from_names(None), [])

    def test_normalize_flavor_deduplicates_while_preserving_order(self):
        self.assertEqual(normalize_flavor('savory, umami, Savory, spicy'), 'savory, umami, spicy')

    def test_normalize_flavor_tags_cleans_bracketed_list_text(self):
        self.assertEqual(
            normalize_flavor_tags("['savory', 'nutrient-dense']"),
            ['savory', 'nutrient-dense'],
        )

    def test_recipe_model_flavor_tags_matches_schema_normalization(self):
        recipe = Recipe(flavor='savory, umami, Savory')
        self.assertEqual(recipe.flavor_tags, ['savory', 'umami'])


class RecipePayloadNormalizationTests(SimpleTestCase):
    """Payload normalization should survive nulls and respect model length limits."""

    def test_json_null_values_fall_back_to_defaults(self):
        payload = normalize_recipe_payload({'title': None, 'description': None, 'cuisine': None})
        self.assertEqual(payload['title'], DEFAULT_RECIPE_TITLE)
        self.assertEqual(payload['description'], '')
        self.assertEqual(payload['cuisine'], DEFAULT_CUISINE)

    def test_json_null_values_fall_back_to_provided_defaults(self):
        payload = normalize_recipe_payload(
            {'title': None},
            defaults={'title': 'Fallback Title'},
        )
        self.assertEqual(payload['title'], 'Fallback Title')

    def test_title_is_clamped_to_recipe_model_max_length(self):
        payload = normalize_recipe_payload({'title': 't' * 500})
        self.assertEqual(len(payload['title']), Recipe._meta.get_field('title').max_length)

    def test_ingredient_fields_are_clamped_to_model_max_lengths(self):
        payload = normalize_recipe_payload(
            {
                'ingredients': [
                    {
                        'name': 'n' * 150,
                        'quantity': 'q' * 80,
                        'unit': 'u' * 40,
                        'alternative': 'a' * 150,
                    },
                ],
            }
        )
        row = payload['ingredients'][0]
        self.assertEqual(len(row['name']), Ingredient._meta.get_field('name').max_length)
        self.assertEqual(len(row['quantity']), Ingredient._meta.get_field('quantity').max_length)
        self.assertEqual(len(row['unit']), Ingredient._meta.get_field('unit').max_length)
        self.assertEqual(len(row['alternative']), Ingredient._meta.get_field('alternative').max_length)
