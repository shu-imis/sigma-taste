"""Shared helpers for AI Recipe Studio handlers."""

import re

from django.shortcuts import render

from core.forms import AIGenerateForm
from core.models import UserPreference
from core.services.recipe import DEFAULT_COOKING_TIME

from ...shared.page_content import AI_STUDIO_HERO_BADGES
from ...shared.panels import build_ai_studio_sidebar_panels

_PREFERENCE_DELIMITERS = re.compile(r'[,，;；\n\r]+')


def _first_preference_value(raw_text: str) -> str:
    for token in _PREFERENCE_DELIMITERS.split(str(raw_text or '')):
        value = token.strip()
        if value:
            return value
    return ''


def _load_user_preference(user):
    if not getattr(user, 'is_authenticated', False):
        return None
    return UserPreference.objects.filter(user=user).first()


def _ai_initial_from_preference(user) -> dict:
    preference = _load_user_preference(user)
    if preference is None:
        return {}

    initial = {}
    flavors = [
        label
        for enabled, label in (
            (preference.spicy, 'spicy'),
            (preference.sweet, 'sweet'),
            (preference.sour, 'sour'),
        )
        if enabled
    ]
    if flavors:
        initial['flavor_preference'] = ', '.join(flavors)

    cuisine = _first_preference_value(preference.preferred_cuisines)
    if cuisine:
        initial['cuisine_preference'] = cuisine

    if preference.health_goal != 'none':
        initial['health_goal'] = preference.get_health_goal_display()

    allergies = str(preference.allergies or '').strip()
    if allergies:
        initial['allergies'] = allergies

    return initial


def build_default_ai_form(request, default_model: str, available_models) -> AIGenerateForm:
    """Build default AI form state for first load and error fallbacks."""
    initial = {'model': default_model, 'cooking_time': DEFAULT_COOKING_TIME}
    initial.update(_ai_initial_from_preference(getattr(request, 'user', None)))
    return AIGenerateForm(initial=initial, available_models=available_models)


def build_ai_form_from_post_data(post_data, *, fallback_model: str = '', available_models=None) -> AIGenerateForm:
    """Rebuild AI form state from POST payload without full-form validation."""
    selected_model = str(post_data.get('model') or fallback_model or '').strip()
    cooking_time = str(post_data.get('cooking_time') or '').strip() or DEFAULT_COOKING_TIME
    return AIGenerateForm(
        initial={
            'model': selected_model,
            'available_ingredients': str(post_data.get('available_ingredients') or ''),
            'cooking_time': cooking_time,
            'flavor_preference': str(post_data.get('flavor_preference') or ''),
            'cuisine_preference': str(post_data.get('cuisine_preference') or ''),
            'health_goal': str(post_data.get('health_goal') or ''),
            'allergies': str(post_data.get('allergies') or ''),
        },
        available_models=available_models,
    )


def parse_available_ingredient_names(raw_text: str) -> list[str]:
    """Parse AI ingredient input from comma/newline separated text into a deduplicated list."""
    raw_value = str(raw_text or '')
    tokens = _PREFERENCE_DELIMITERS.split(raw_value)
    parsed: list[str] = []
    seen = set()
    for token in tokens:
        item = token.strip()
        if not item:
            continue
        item = re.sub(r'^(?:[-*•]\s*|\d+\s*[.)、]\s*)', '', item).strip()
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        parsed.append(item)
    return parsed


def render_ai_generate_page(
    request,
    *,
    form,
    generated_recipe,
    generated_model: str,
    publish_token: str,
    publish_draft_id: str,
    available_models,
):
    """Render AI Studio page with the shared template context."""
    return render(
        request,
        'core/pages/ai/studio.html',
        {
            'form': form,
            'generated_recipe': generated_recipe,
            'generated_model': generated_model,
            'publish_token': publish_token,
            'publish_draft_id': publish_draft_id,
            'available_models': available_models,
            'hero_badges': AI_STUDIO_HERO_BADGES,
            'ai_studio_sidebar_panels': build_ai_studio_sidebar_panels(),
        },
    )
