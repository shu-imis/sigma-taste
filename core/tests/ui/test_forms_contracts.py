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
    ContentReportForm,
    ContentReportResolveForm,
    PreferenceForm,
    RecipeCreateForm,
    ReviewForm,
    UserProfileForm,
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

    def test_recipe_create_tutorial_video_url_matches_model_length_cap(self):
        form = RecipeCreateForm()
        self.assertEqual(form.fields['tutorial_video_url'].max_length, 200)

        overlong = RecipeCreateForm(
            data={
                'title': 'Overlong Video Link',
                'cuisine': 'Home Style',
                'cooking_time': 20,
                'difficulty': 'easy',
                'steps_text': '1. Cook',
                'ingredients_text': 'Noodles,200,g,',
                'tutorial_video_url': 'https://example.com/' + 'a' * 200,
            }
        )
        self.assertFalse(overlong.is_valid())
        self.assertIn('tutorial_video_url', overlong.errors)

    def test_ai_generate_input_length_caps_contract(self):
        form = AIGenerateForm(available_models=['qwen2.5:7b'])
        self.assertEqual(form.fields['available_ingredients'].max_length, TEXTAREA_INPUT_MAX_LENGTH)
        self.assertEqual(form.fields['allergies'].max_length, 500)

    def test_ai_generate_rejects_overlong_available_ingredients(self):
        form = AIGenerateForm(
            data={
                'model': 'qwen2.5:7b',
                'available_ingredients': 'egg, ' * (TEXTAREA_INPUT_MAX_LENGTH // 2),
                'cooking_time': 20,
            },
            available_models=['qwen2.5:7b'],
        )
        self.assertFalse(form.is_valid())
        self.assertIn('available_ingredients', form.errors)

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

    def test_optional_field_labels_use_parenthesized_suffix_convention(self):
        recipe_form = RecipeCreateForm()
        self.assertEqual(recipe_form.fields['description'].label, 'Description (optional)')
        self.assertEqual(recipe_form.fields['flavor'].label, 'Flavor (optional)')
        self.assertEqual(recipe_form.fields['tutorial_video_url'].label, 'Tutorial video link (optional)')

        ai_form = AIGenerateForm(available_models=['qwen2.5:7b'])
        for field_name in ('flavor_preference', 'cuisine_preference', 'health_goal'):
            with self.subTest(field=field_name):
                self.assertTrue(ai_form.fields[field_name].label.endswith(' (optional)'))

        profile_form = UserProfileForm()
        self.assertEqual(profile_form.fields['bio'].label, 'Bio (optional)')

        preference_form = PreferenceForm()
        self.assertEqual(preference_form.fields['allergies'].label, 'Allergies (optional)')
        self.assertEqual(preference_form.fields['preferred_cuisines'].label, 'Preferred cuisines (optional)')

        report_form = ContentReportForm()
        self.assertEqual(report_form.fields['details'].label, 'Report details (optional)')

        resolve_form = ContentReportResolveForm()
        self.assertEqual(resolve_form.fields['resolution_note'].label, 'Resolution note (optional)')

        review_form = ReviewForm()
        self.assertEqual(review_form.fields['content'].label, 'Content (optional)')
