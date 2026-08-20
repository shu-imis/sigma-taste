"""Recipe creation and review forms."""

from django import forms

from core.models import Review

from .constants import (
    DIFFICULTY_CHOICES,
    FORM_COOKING_TIME_MAX,
    FORM_COOKING_TIME_MIN,
    FORM_INGREDIENTS_ROWS,
    FORM_STEPS_ROWS,
    FORM_TEXTAREA_ROWS_COMPACT,
    HELP_INGREDIENTS_TEXT,
    HELP_STEPS_TEXT,
    PLACEHOLDER_INGREDIENTS_TEXT,
    PLACEHOLDER_REVIEW_CONTENT,
    PLACEHOLDER_STEPS_TEXT,
)

TEXTAREA_INPUT_MAX_LENGTH = 10000


class RecipeCreateForm(forms.Form):
    """Recipe submission form used by the website create page."""

    title = forms.CharField(max_length=200, label='Title')
    description = forms.CharField(
        label='Description',
        widget=forms.Textarea(attrs={'rows': FORM_TEXTAREA_ROWS_COMPACT}),
        required=False,
    )
    cuisine = forms.CharField(max_length=50, label='Cuisine')
    flavor = forms.CharField(max_length=100, required=False, label='Flavor')
    cooking_time = forms.IntegerField(
        min_value=FORM_COOKING_TIME_MIN,
        max_value=FORM_COOKING_TIME_MAX,
        label='Cooking time (min)',
    )
    difficulty = forms.ChoiceField(choices=DIFFICULTY_CHOICES, label='Difficulty')
    steps_text = forms.CharField(
        label='Steps',
        help_text=HELP_STEPS_TEXT,
        max_length=TEXTAREA_INPUT_MAX_LENGTH,
        widget=forms.Textarea(
            attrs={
                'rows': FORM_STEPS_ROWS,
                'placeholder': PLACEHOLDER_STEPS_TEXT,
            }
        ),
    )
    ingredients_text = forms.CharField(
        label='Ingredients',
        help_text=HELP_INGREDIENTS_TEXT,
        max_length=TEXTAREA_INPUT_MAX_LENGTH,
        widget=forms.Textarea(
            attrs={
                'rows': FORM_INGREDIENTS_ROWS,
                'placeholder': PLACEHOLDER_INGREDIENTS_TEXT,
            }
        ),
    )
    source_draft_id = forms.CharField(required=False, widget=forms.HiddenInput())
    source_draft_token = forms.CharField(required=False, widget=forms.HiddenInput())


class ReviewForm(forms.ModelForm):
    """Review form for recipe detail page."""

    class Meta:
        model = Review
        fields = ('rating', 'content', 'is_anonymous')
        widgets = {
            'rating': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'content': forms.Textarea(
                attrs={
                    'rows': FORM_TEXTAREA_ROWS_COMPACT,
                    'placeholder': PLACEHOLDER_REVIEW_CONTENT,
                }
            ),
        }
