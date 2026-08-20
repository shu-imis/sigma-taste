"""Contract tests for form field copy and bounds."""

from django import forms
from django.test import SimpleTestCase

from core.forms import (
    FORM_COOKING_TIME_MAX,
    FORM_COOKING_TIME_MIN,
    HELP_INGREDIENTS_TEXT,
    HELP_STEPS_TEXT,
    PLACEHOLDER_AVAILABLE_INGREDIENTS,
    PLACEHOLDER_INGREDIENTS_TEXT,
    PLACEHOLDER_STEPS_TEXT,
    AIGenerateForm,
    RecipeCreateForm,
)
from core.forms.recipe import TEXTAREA_INPUT_MAX_LENGTH


class FormContractTests(SimpleTestCase):
    """Critical form copy and validation bounds should stay stable."""

    def test_recipe_create_copy_contract(self):
        form = RecipeCreateForm()
        self.assertEqual(form.fields['steps_text'].help_text, HELP_STEPS_TEXT)
        self.assertEqual(form.fields['ingredients_text'].help_text, HELP_INGREDIENTS_TEXT)
        self.assertEqual(form.fields['steps_text'].widget.attrs.get('placeholder'), PLACEHOLDER_STEPS_TEXT)
        self.assertEqual(form.fields['ingredients_text'].widget.attrs.get('placeholder'), PLACEHOLDER_INGREDIENTS_TEXT)

    def test_ai_generate_copy_contract(self):
        form = AIGenerateForm(available_models=['qwen2.5:7b'])
        self.assertIsInstance(form.fields['model'].widget, forms.Select)
        self.assertEqual(form.fields['model'].widget.choices, [('qwen2.5:7b', 'qwen2.5:7b')])
        self.assertEqual(
            form.fields['available_ingredients'].widget.attrs.get('placeholder'),
            PLACEHOLDER_AVAILABLE_INGREDIENTS,
        )

    def test_cooking_time_bounds_contract(self):
        recipe_form = RecipeCreateForm()
        ai_form = AIGenerateForm(available_models=['qwen2.5:7b'])
        self.assertEqual(recipe_form.fields['cooking_time'].min_value, FORM_COOKING_TIME_MIN)
        self.assertEqual(recipe_form.fields['cooking_time'].max_value, FORM_COOKING_TIME_MAX)
        self.assertEqual(ai_form.fields['cooking_time'].min_value, FORM_COOKING_TIME_MIN)
        self.assertEqual(ai_form.fields['cooking_time'].max_value, FORM_COOKING_TIME_MAX)

    def test_recipe_create_textarea_length_caps_contract(self):
        form = RecipeCreateForm()
        self.assertEqual(form.fields['steps_text'].max_length, TEXTAREA_INPUT_MAX_LENGTH)
        self.assertEqual(form.fields['ingredients_text'].max_length, TEXTAREA_INPUT_MAX_LENGTH)

    def test_recipe_create_textareas_reject_overlong_input(self):
        form = RecipeCreateForm(
            data={
                'title': 'Overlong Steps',
                'cuisine': 'Home Style',
                'cooking_time': 20,
                'difficulty': 'easy',
                'steps_text': 'x' * (TEXTAREA_INPUT_MAX_LENGTH + 1),
                'ingredients_text': 'Noodles,200,g,',
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn('steps_text', form.errors)
