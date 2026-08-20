"""Simple cache helpers for ranking snapshots."""

from django.core.cache import cache
from django.utils import timezone

from .engine import calculate_rankings

RANKING_CACHE_TTL_SECONDS = 60
RANKING_TYPES = ('red', 'black', 'ai')
RANKING_WINDOWS = ('day', 'week', 'month')


def cache_key(rank_type: str, window: str) -> str:
    """Build the cache key for one ranking snapshot."""
    return f'ranking:snapshot:{rank_type}:{window}'


def build_snapshot(rank_type: str, window: str):
    """Load one ranking snapshot from cache or compute it directly."""
    key = cache_key(rank_type, window)
    snapshot = cache.get(key)
    if snapshot is not None:
        return snapshot

    snapshot = {
        'data': calculate_rankings(rank_type, window),
        'generated_at': timezone.now(),
    }
    cache.set(key, snapshot, timeout=RANKING_CACHE_TTL_SECONDS)
    return snapshot


def invalidate_cache() -> None:
    """Clear all cached board snapshots after ranking-relevant writes."""
    cache.delete_many([cache_key(rank_type, window) for rank_type in RANKING_TYPES for window in RANKING_WINDOWS])
