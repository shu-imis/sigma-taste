"""Form exports for website pages."""

from .ai import AIGenerateForm
from .auth import LoginForm, RegisterForm
from .constants import (
    FORM_COOKING_TIME_MAX,
    FORM_COOKING_TIME_MIN,
    HELP_INGREDIENTS_TEXT,
    HELP_STEPS_TEXT,
    PLACEHOLDER_AVAILABLE_INGREDIENTS,
    PLACEHOLDER_INGREDIENTS_TEXT,
    PLACEHOLDER_STEPS_TEXT,
)
from .profile import PreferenceForm, UserProfileForm
from .recipe import RecipeCreateForm, ReviewForm

__all__ = [
    'RegisterForm',
    'LoginForm',
    'UserProfileForm',
    'PreferenceForm',
    'RecipeCreateForm',
    'ReviewForm',
    'AIGenerateForm',
    'FORM_COOKING_TIME_MIN',
    'FORM_COOKING_TIME_MAX',
    'HELP_STEPS_TEXT',
    'HELP_INGREDIENTS_TEXT',
    'PLACEHOLDER_AVAILABLE_INGREDIENTS',
    'PLACEHOLDER_STEPS_TEXT',
    'PLACEHOLDER_INGREDIENTS_TEXT',
]
