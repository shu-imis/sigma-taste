"""Shared sidebar panel payloads for consistent page-side presentation."""

from __future__ import annotations

import re

from django.urls import reverse

from core.templatetags.number_format import compact_number
from core.text_utils import contains_cjk_text

__all__ = [
    'build_ai_studio_sidebar_panels',
    'build_home_sidebar_panels',
    'build_profile_sidebar_panels',
    'build_recipe_studio_sidebar_panels',
]

_CJK_NAME_PART_RE = re.compile(r'^[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\s·•．・]+$')


def _is_fully_cjk_name_part(text: str) -> bool:
    """Return whether a name part is entirely composed of CJK name characters."""
    clean_text = (text or '').strip()
    return bool(clean_text) and bool(_CJK_NAME_PART_RE.fullmatch(clean_text))


def _build_profile_display_name(user) -> tuple[str, str | None]:
    """
    Build the profile snapshot display name.

    Chinese names read more naturally in surname-given order without a space and
    benefit from a separate typographic treatment in the UI. Mixed-script names
    should keep the user's input order instead of being forced into Chinese order.
    """
    first_name = (getattr(user, 'first_name', '') or '').strip()
    last_name = (getattr(user, 'last_name', '') or '').strip()
    has_cjk_name = contains_cjk_text(first_name) or contains_cjk_text(last_name)

    if _is_fully_cjk_name_part(first_name) and _is_fully_cjk_name_part(last_name):
        display_name = ''.join(part for part in (last_name, first_name) if part)
        return display_name or user.username, 'cjk'

    if has_cjk_name:
        display_name = ' '.join(part for part in (first_name, last_name) if part)
        return display_name or user.username, 'mixed'

    return user.get_full_name() or user.username, None


def build_home_sidebar_panels(hot_recipes) -> list[dict]:
    """Build the Discover page sidebar panels."""
    hot_entries = [
        {
            'title': recipe.title,
            'href': reverse('web-recipe-detail', args=[recipe.id]),
            'meta': f'{compact_number(recipe.view_count)} views',
        }
        for recipe in hot_recipes
    ]
    return [
        {
            'kind': 'link-list',
            'heading_level': '3',
            'title': 'Rising now',
            'subtitle': 'Recipes people are paying attention to right now.',
            'entries': hot_entries,
            'empty_text': 'Recipes gathering interest will appear here as people cook and return.',
        },
        {
            'kind': 'action-list',
            'heading_level': '3',
            'title': 'Next best moves',
            'subtitle': 'A few thoughtful ways to move from looking to making.',
            'entries': [
                {
                    'label': 'Start an AI draft',
                    'href': reverse('web-ai-generate'),
                    'tone': 'primary',
                },
                {
                    'label': 'Open the boards',
                    'href': reverse('web-boards'),
                    'tone': 'ghost',
                },
                {
                    'label': 'Refine my profile',
                    'href': reverse('web-profile'),
                    'tone': 'ghost',
                },
            ],
        },
    ]


def build_profile_sidebar_panels(user, preference) -> list[dict]:
    """Build the Profile page sidebar panels."""
    display_name, title_variant = _build_profile_display_name(user)
    flavor_badges = [
        label
        for enabled, label in (
            (getattr(preference, 'spicy', False), 'Spicy'),
            (getattr(preference, 'sweet', False), 'Sweet'),
            (getattr(preference, 'sour', False), 'Sour'),
        )
        if enabled
    ]
    return [
        {
            'kind': 'summary-stack',
            'title': 'Profile snapshot',
            'subtitle': 'A clear read on how your account comes across right now.',
            'sections': [
                {
                    'title': display_name,
                    'title_is_cjk': title_variant == 'cjk',
                    'title_is_cjk_mixed': title_variant == 'mixed',
                    'meta': f'@{user.username} · Joined {user.date_joined:%Y-%m-%d}',
                    'body': getattr(user, 'bio', '')
                    or 'Add a short kitchen perspective so your recipes feel personal and recognizably yours.',
                },
                {
                    'kicker': 'Flavor profile',
                    'badges': flavor_badges,
                    'empty_message': 'No flavor notes yet.',
                },
                {
                    'kicker': 'Preference notes',
                    'rows': [
                        {
                            'label': 'Health goal',
                            'value': preference.get_health_goal_display(),
                        },
                        {
                            'label': 'Allergies',
                            'value': preference.allergies or 'Nothing listed yet.',
                        },
                        {
                            'label': 'Preferred cuisines',
                            'value': preference.preferred_cuisines or 'Nothing listed yet.',
                        },
                    ],
                },
            ],
        },
        {
            'kind': 'info-list',
            'title': 'What this shapes',
            'subtitle': 'How this page supports the rest of your presence on the site.',
            'entries': [
                {
                    'title': 'Author presence',
                    'body': 'Your name and bio help each recipe feel personal and accountable.',
                },
                {
                    'title': 'Taste direction',
                    'body': 'Flavor signals give future drafts and browsing a clearer point of view.',
                },
                {
                    'title': 'Dietary clarity',
                    'body': 'Allergies and cuisine preferences help keep your profile honest and usable.',
                },
            ],
        },
    ]


def build_recipe_studio_sidebar_panels() -> list[dict]:
    """Build the Recipe Studio page sidebar panels."""
    return [
        {
            'kind': 'info-list',
            'title': 'What thoughtful drafts do',
            'subtitle': 'A few small choices can make a recipe feel ready for another person to use.',
            'entries': [
                {
                    'title': 'Name the dish clearly',
                    'body': 'A precise title helps people understand what they are about to cook.',
                },
                {
                    'title': 'Write steps someone can follow',
                    'body': 'Short, ordered actions make the method easier to trust in a real kitchen.',
                },
                {
                    'title': 'Complete each ingredient line',
                    'body': 'Amounts, units, and alternatives reduce guesswork for the next cook.',
                },
            ],
        },
        {
            'kind': 'info-list',
            'title': 'Before you share',
            'subtitle': 'Recipe Studio is the last editing pass before a draft becomes public.',
            'entries': [
                {
                    'title': 'Tighten the title',
                    'body': 'A specific name helps the recipe feel intentional before anyone opens it.',
                },
                {
                    'title': 'Check the ingredient lines',
                    'body': 'Complete quantities and alternatives make the page easier to trust at a glance.',
                },
                {
                    'title': 'Read the flow aloud',
                    'body': 'If the method sounds natural from start to finish, the draft is usually ready to share.',
                },
            ],
        },
    ]


def build_ai_studio_sidebar_panels() -> list[dict]:
    """Build the AI Recipe Studio page sidebar panels."""
    return [
        {
            'kind': 'info-list',
            'title': 'Best inputs start here',
            'subtitle': 'A few grounded constraints help the draft feel more thoughtful and believable.',
            'entries': [
                {
                    'title': 'Name the ingredients clearly',
                    'body': 'Use ingredient names you would genuinely expect to find in a home kitchen.',
                },
                {
                    'title': 'Set a believable time',
                    'body': 'A realistic time frame helps the draft stay honest about the work involved.',
                },
                {
                    'title': 'Give a taste direction',
                    'body': 'Cuisine, flavor, and health goals help the draft reflect a point of view.',
                },
            ],
        },
        {
            'kind': 'info-list',
            'title': 'What you get back',
            'subtitle': 'The draft is meant to be read, adjusted, and saved when it feels right.',
            'entries': [
                {
                    'title': 'Recipe framing',
                    'body': 'Title, description, cuisine, timing, and difficulty arrive as one readable whole.',
                },
                {
                    'title': 'Cookable structure',
                    'body': 'Ingredient lines and ordered steps make it easier to judge whether the draft can really be cooked.',
                },
                {
                    'title': 'A save-ready version',
                    'body': 'When the draft feels right, you can keep it as a full recipe page in one step.',
                },
            ],
        },
    ]
