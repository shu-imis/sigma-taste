"""Shared helpers for the test suite."""

import secrets
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache

from core.models import Recipe
from core.views.shared.ai import (
    AI_DRAFT_MAX_AGE_SECONDS,
    AI_DRAFT_SIGNING_SALT,
    ai_draft_cache_key,
)


def find_core_dir() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        has_models_module = (parent / 'models.py').exists() or (parent / 'models').is_dir()
        if parent.name == 'core' and has_models_module:
            return parent
    raise RuntimeError('Unable to locate core package root from test path.')


def make_user(*, role='member', **overrides):
    """Create a user with suite-standard identity defaults, overridable per call."""
    defaults = {
        'username': 'test-user',
        'email': 'test-user@example.com',
        'first_name': 'Test',
        'last_name': 'User',
        'password': 'pwd-12345',
    }
    defaults.update(overrides)
    manager = get_user_model().objects
    if role == 'member':
        return manager.create_user(**defaults)
    if role == 'steward':
        return manager.create_steward_user(**defaults)
    raise ValueError(f'Unknown role: {role}')


def make_recipe(*, author, **overrides):
    """Create a recipe with suite-standard defaults, overridable per call."""
    defaults = {
        'title': 'Test Recipe',
        'description': 'Test fixture.',
        'cuisine': 'Home Style',
        'flavor': 'savory',
        'steps': ['Step 1'],
        'cooking_time': 20,
        'difficulty': 'easy',
        'nutrition': {},
    }
    defaults.update(overrides)
    return Recipe.objects.create(author=author, **defaults)


def force_session_key(client):
    """Write a throwaway session key so the test client gets a real session_key."""
    session = client.session
    session['test_session_marker'] = True
    session.save()
    return session.session_key


def make_ai_draft_bundle(
    *,
    session_key,
    user_id,
    generated_recipe,
    source_payload,
    draft_id=None,
    model='test-model:1',
):
    """Cache an AI draft payload and return its (draft_id, signed token) pair."""
    draft_id = draft_id or secrets.token_urlsafe(24)
    cache.set(
        ai_draft_cache_key(draft_id),
        {
            'generated_recipe': generated_recipe,
            'source_payload': source_payload,
            'model': model,
        },
        timeout=AI_DRAFT_MAX_AGE_SECONDS,
    )
    draft_token = signing.dumps(
        {
            'draft_id': draft_id,
            'session_key': session_key,
            'issued_for_user_id': user_id,
        },
        salt=AI_DRAFT_SIGNING_SALT,
        compress=True,
    )
    return draft_id, draft_token
