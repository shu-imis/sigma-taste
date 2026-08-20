"""Shared page content payloads for repeated template structures."""

from __future__ import annotations

from django.urls import reverse

from core.templatetags.number_format import compact_number
from core.templatetags.ui_copy import to_ui_title

DISCOVER_HERO_BADGES = [
    'Trusted home recipes',
    'AI-assisted drafts',
    'Shared kitchen notes',
]

BOARDS_HERO_BADGES = [
    'Recipes people revisit',
    'Recipes under discussion',
    'AI drafts to watch',
]

PROFILE_HERO_BADGES = [
    'Personal identity',
    'Taste signals',
    'Dietary notes',
]

RECIPE_STUDIO_HERO_BADGES = [
    'Clear titles',
    'Practical steps',
    'Ready to share',
]

AI_STUDIO_HERO_BADGES = [
    'What is on hand',
    'Realistic timing',
    'Drafts you can shape',
]


def build_home_empty_state() -> dict:
    """Build the Discover page empty-state payload."""
    return {
        'kicker': 'A quieter moment',
        'title': 'No recipes match this combination yet',
        'copy': (
            'Try widening the search, look at what people are returning to on the boards, '
            'or make room for the dish you would like to share here.'
        ),
        'facts': [
            {
                'title': 'Open the search',
                'body': 'Try fewer filters or return to the latest recipes.',
            },
            {
                'title': 'Follow the signals',
                'body': 'See which recipes are drawing attention and response on the boards.',
            },
            {
                'title': 'Start the draft',
                'body': 'Turn a dish you care about into a page others can cook from.',
            },
        ],
        'actions': [
            {
                'label': 'Reset search',
                'href': reverse('web-home'),
                'tone': 'ghost',
            },
            {
                'label': 'Start a recipe draft',
                'href': reverse('web-recipe-create'),
                'tone': 'primary',
            },
            {
                'label': 'Visit the boards',
                'href': reverse('web-boards'),
                'tone': 'ghost',
            },
        ],
    }


def build_boards_empty_state(ranking) -> dict:
    """Build the Boards page empty-state payload."""
    return {
        'kicker': 'A quieter board',
        'title': 'This board is still taking shape',
        'copy': (
            'Board positions become clearer as people cook, return, and leave notes. '
            'Try a wider time window or head back to Discover to help the next recipe gather momentum.'
        ),
        'facts': [
            {
                'title': ranking.get_type_display(),
                'body': 'Current board lens',
            },
            {
                'title': ranking.get_window_display(),
                'body': 'Time window',
            },
            {
                'title': ranking.generated_at.strftime('%Y-%m-%d %H:%M'),
                'body': 'Last refreshed',
            },
        ],
        'actions': [
            {
                'label': 'View a wider snapshot',
                'href': f"{reverse('web-boards')}?type=red&window=month",
                'tone': 'primary',
            },
            {
                'label': 'Return to discover',
                'href': reverse('web-home'),
                'tone': 'ghost',
            },
        ],
    }


def build_recipe_detail_hero_meta_tokens(recipe) -> list[str]:
    """Build the Recipe Detail hero meta tokens."""
    return [
        to_ui_title(recipe.cuisine),
        f'{recipe.cooking_time} min',
        to_ui_title(recipe.get_difficulty_display()),
        f'{compact_number(recipe.view_count)} views',
    ]


def build_recipe_detail_hero_meta_note(recipe) -> str:
    """Build the softer trailing note for recipe detail hero metadata."""
    author_name = recipe.author.username if getattr(recipe, 'author', None) else 'Anonymous'
    return f'Shared by {author_name}'


def build_recipe_detail_hero_badges(recipe, *, can_manage_recipe: bool) -> list[str]:
    """Build the Recipe Detail hero badges."""
    badges = [str(tag).strip() for tag in (getattr(recipe, 'flavor_tags', []) or []) if str(tag).strip()]
    if recipe.is_ai_generated:
        badges.append('AI assisted')
    if recipe.status != 'published' or can_manage_recipe:
        badges.append(f'Status: {recipe.get_status_display()}')
    return badges
