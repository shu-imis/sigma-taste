"""Profile and preference forms."""

from django import forms
from django.contrib.auth import get_user_model

from core.models import UserPreference

from .constants import (
    FORM_TEXTAREA_ROWS_COMPACT,
    PLACEHOLDER_ALLERGIES,
    PLACEHOLDER_PREFERRED_CUISINES,
)

USER_MODEL = get_user_model()


class UserProfileForm(forms.ModelForm):
    """User profile editor for basic personal fields."""

    class Meta:
        model = USER_MODEL
        fields = ('first_name', 'last_name', 'bio')
        labels = {
            'first_name': 'First name',
            'last_name': 'Last name',
            'bio': 'Bio',
        }
        widgets = {
            'bio': forms.Textarea(attrs={'rows': FORM_TEXTAREA_ROWS_COMPACT}),
        }


class PreferenceForm(forms.ModelForm):
    """Taste and dietary preference editor."""

    class Meta:
        model = UserPreference
        fields = ('spicy', 'sweet', 'sour', 'allergies', 'preferred_cuisines', 'health_goal')
        labels = {
            'allergies': 'Allergies',
            'preferred_cuisines': 'Preferred cuisines',
            'health_goal': 'Health goal',
        }
        widgets = {
            'allergies': forms.TextInput(attrs={'placeholder': PLACEHOLDER_ALLERGIES}),
            'preferred_cuisines': forms.TextInput(attrs={'placeholder': PLACEHOLDER_PREFERRED_CUISINES}),
        }
