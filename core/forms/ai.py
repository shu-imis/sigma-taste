"""AI generation forms."""

from django import forms

from .constants import (
    FORM_COOKING_TIME_MAX,
    FORM_COOKING_TIME_MIN,
    FORM_TEXTAREA_ROWS_COMPACT,
    PLACEHOLDER_AVAILABLE_INGREDIENTS,
)
from .recipe import TEXTAREA_INPUT_MAX_LENGTH

AI_ALLERGIES_MAX_LENGTH = 500


class AIGenerateForm(forms.Form):
    """Input form for AI-assisted recipe generation."""

    model = forms.CharField(
        max_length=120,
        required=True,
        label='Model',
        widget=forms.Select(),
    )
    available_ingredients = forms.CharField(
        max_length=TEXTAREA_INPUT_MAX_LENGTH,
        label='Available ingredients',
        widget=forms.Textarea(attrs={'rows': FORM_TEXTAREA_ROWS_COMPACT, 'placeholder': PLACEHOLDER_AVAILABLE_INGREDIENTS}),
    )
    cooking_time = forms.IntegerField(min_value=FORM_COOKING_TIME_MIN, max_value=FORM_COOKING_TIME_MAX, label='Cooking time (min)')
    flavor_preference = forms.CharField(max_length=50, required=False, label='Flavor preference (optional)')
    cuisine_preference = forms.CharField(max_length=50, required=False, label='Cuisine preference (optional)')
    health_goal = forms.CharField(max_length=50, required=False, label='Health goal (optional)')
    allergies = forms.CharField(required=False, max_length=AI_ALLERGIES_MAX_LENGTH, widget=forms.HiddenInput())

    def __init__(self, *args, available_models=None, **kwargs):
        """Bind detected local models into the select widget."""
        super().__init__(*args, **kwargs)
        models = [str(model).strip() for model in (available_models or []) if str(model).strip()]
        if models:
            self.fields['model'].widget.choices = [(model, model) for model in models]
            self.fields['model'].widget.attrs.pop('disabled', None)
        else:
            self.fields['model'].widget.choices = [('', 'Unavailable')]
            self.fields['model'].widget.attrs['disabled'] = 'disabled'
