"""AI draft helpers for web views."""

import secrets
from typing import Any

from django.core import signing
from django.core.cache import cache

AI_DRAFT_SIGNING_SALT = 'core.ai.draft'
AI_DRAFT_MAX_AGE_SECONDS = 30 * 60
AI_DRAFT_CACHE_KEY_PREFIX = 'ai-draft'
AI_DRAFT_CONSUMED_KEY_PREFIX = 'ai-draft-consumed'

__all__ = [
    'AI_DRAFT_MAX_AGE_SECONDS',
    'AI_DRAFT_SIGNING_SALT',
    'consume_ai_draft_payload',
    'issue_ai_draft',
    'peek_ai_draft_payload',
    'load_ai_draft_payload',
]


def ai_draft_cache_key(draft_id: str) -> str:
    """Build cache key for temporary AI draft payload."""
    return f'{AI_DRAFT_CACHE_KEY_PREFIX}:{draft_id}'


def ai_draft_consumed_key(draft_id: str) -> str:
    """Build cache key indicating one-time draft consumption."""
    return f'{AI_DRAFT_CONSUMED_KEY_PREFIX}:{draft_id}'


def consume_ai_draft_payload(draft_id: str) -> dict[str, Any] | None:
    """Atomically mark draft as consumed and return payload once."""
    consumed_key = ai_draft_consumed_key(draft_id)
    if not cache.add(consumed_key, 1, timeout=AI_DRAFT_MAX_AGE_SECONDS):
        return None
    payload = cache.get(ai_draft_cache_key(draft_id))
    if not isinstance(payload, dict):
        return None
    cache.delete(ai_draft_cache_key(draft_id))
    return payload


def peek_ai_draft_payload(draft_id: str) -> dict[str, Any] | None:
    """Read draft payload without consuming one-time publish eligibility."""
    payload = cache.get(ai_draft_cache_key(draft_id))
    if not isinstance(payload, dict):
        return None
    return payload


def issue_ai_draft(
    *,
    request,
    generated_recipe: dict[str, Any],
    source_payload: dict[str, Any],
    model: str,
) -> tuple[str, str]:
    """Store generated AI draft server-side and return signed publish token."""
    if request.session.session_key is None:
        request.session.save()

    draft_id = secrets.token_urlsafe(24)
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
            'session_key': request.session.session_key,
            'issued_for_user_id': request.user.id if request.user.is_authenticated else None,
        },
        salt=AI_DRAFT_SIGNING_SALT,
        compress=True,
    )
    return draft_id, draft_token


def load_ai_draft_payload(request, *, draft_token: str, draft_id: str, consume: bool):
    """Validate a signed AI draft token and return the stored draft payload."""
    signed_payload = signing.loads(
        draft_token,
        salt=AI_DRAFT_SIGNING_SALT,
        max_age=AI_DRAFT_MAX_AGE_SECONDS,
    )
    if not isinstance(signed_payload, dict):
        raise ValueError

    signed_draft_id = str(signed_payload.get('draft_id') or '')
    if not signed_draft_id or signed_draft_id != draft_id:
        raise ValueError

    expected_session_key = str(signed_payload.get('session_key') or '')
    current_session_key = request.session.session_key or ''
    if not expected_session_key or expected_session_key != current_session_key:
        raise ValueError

    issued_for_user_id = signed_payload.get('issued_for_user_id')
    if issued_for_user_id is not None and issued_for_user_id != request.user.id:
        raise ValueError

    draft_payload = consume_ai_draft_payload(draft_id) if consume else peek_ai_draft_payload(draft_id)
    if not isinstance(draft_payload, dict):
        raise ValueError
    generated_recipe = draft_payload.get('generated_recipe')
    source_payload = draft_payload.get('source_payload') or {}
    generated_model = str(draft_payload.get('model') or '').strip()
    if not isinstance(generated_recipe, dict) or not isinstance(source_payload, dict):
        raise ValueError
    return generated_recipe, source_payload, generated_model
