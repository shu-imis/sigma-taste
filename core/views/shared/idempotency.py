"""Shared idempotency helpers for write endpoints."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from django.conf import settings
from django.core.cache import cache

_INFLIGHT_STATE = 'inflight'
_INFLIGHT_TTL_DEFAULT_SECONDS = 45


def canonical_payload_digest(payload: dict[str, Any]) -> str:
    """Build deterministic hash for a canonical payload dictionary."""
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    ).hexdigest()


def inflight_marker() -> dict[str, str]:
    """Return the canonical in-flight marker object."""
    return {'state': _INFLIGHT_STATE}


def acquire_inflight_lock(key: str, *, timeout: int) -> bool:
    """Try acquiring an in-flight lock for an idempotency key."""
    return cache.add(key, inflight_marker(), timeout=max(int(timeout), 1))


def read_idempotency_value(key: str) -> Any:
    """Read current value for an idempotency key."""
    return cache.get(key)


def clear_idempotency_key(key: str) -> None:
    """Delete an idempotency key from cache."""
    cache.delete(key)


def idempotency_ttl_seconds(setting_name: str) -> int:
    """Read an idempotency window (in seconds) from settings, clamped to at least one second."""
    return max(int(getattr(settings, setting_name, _INFLIGHT_TTL_DEFAULT_SECONDS)), 1)


__all__ = [
    'acquire_inflight_lock',
    'canonical_payload_digest',
    'clear_idempotency_key',
    'idempotency_ttl_seconds',
    'read_idempotency_value',
]
