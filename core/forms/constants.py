"""Shared constants for web forms."""

from core.models import Recipe

FORM_TEXTAREA_ROWS_COMPACT = 3
FORM_STEPS_ROWS = 8
FORM_INGREDIENTS_ROWS = 6
FORM_COOKING_TIME_MIN = 5
FORM_COOKING_TIME_MAX = 240

PLACEHOLDER_EXAMPLE_PREFIX = 'Example: '
PLACEHOLDER_ALLERGIES = f'{PLACEHOLDER_EXAMPLE_PREFIX}peanuts, shrimp'
PLACEHOLDER_PREFERRED_CUISINES = f'{PLACEHOLDER_EXAMPLE_PREFIX}home-style, Mediterranean'
PLACEHOLDER_AVAILABLE_INGREDIENTS = f'{PLACEHOLDER_EXAMPLE_PREFIX}eggs, tomato, scallion'
PLACEHOLDER_REVIEW_CONTENT = 'Share what this recipe was like in your kitchen'

HELP_STEPS_TEXT = 'Write one step per line so the flow is easy to follow.'
HELP_INGREDIENTS_TEXT = 'List one ingredient per line: name, quantity, unit, alternative (optional).'
PLACEHOLDER_STEPS_TEXT = (
    f'{HELP_STEPS_TEXT}\n'
    'Example:\n'
    '1. Prep ingredients\n'
    '2. Warm the pan and oil\n'
    '3. Stir-fry and plate'
)
PLACEHOLDER_INGREDIENTS_TEXT = (
    f'{HELP_INGREDIENTS_TEXT}\n'
    'Example:\n'
    'Chicken breast,300,g,Chicken thigh\n'
    'Green pepper,1,pc,\n'
    'Garlic,3,cloves,'
)

# The Recipe model owns the canonical difficulty enum.
DIFFICULTY_CHOICES = Recipe.DIFFICULTY_CHOICES
