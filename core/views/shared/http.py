"""HTTP helpers shared by page-level handlers."""

import logging

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.db.models import Q, TextField
from django.db.models.functions import Cast
from django.http import HttpRequest

logger = logging.getLogger(__name__)

__all__ = [
    'MAX_SEARCH_QUERY_LENGTH',
    'apply_recipe_search',
    'build_querystring_excluding',
    'consume_login_account_rate_limit',
    'consume_rate_limit',
    'get_client_ip',
    'rate_limit_config',
]

MAX_SEARCH_QUERY_LENGTH = 100


def _fallback_recipe_search(queryset, q: str):
    """Apply case-insensitive fallback search for non-PostgreSQL backends."""
    return (
        queryset.annotate(search_steps_text=Cast('steps', output_field=TextField()))
        .filter(
            Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(ingredients__name__icontains=q)
            | Q(search_steps_text__icontains=q)
        )
        .distinct()
    )


def build_querystring_excluding(request: HttpRequest, *keys: str) -> str:
    """Return URL-encoded query string after dropping provided keys."""
    params = request.GET.copy()
    for key in keys:
        params.pop(key, None)
    return params.urlencode()


def apply_recipe_search(queryset, q: str):
    """Apply full-text search on PostgreSQL with cross-database fallback."""
    if not q:
        return queryset, False

    q = q[:MAX_SEARCH_QUERY_LENGTH]

    if connection.vendor == 'postgresql':
        try:
            from django.contrib.postgres.search import (
                SearchQuery,
                SearchRank,
                SearchVector,
            )
        except Exception:
            return _fallback_recipe_search(queryset, q), False

        search_vector = SearchVector('title', weight='A') + SearchVector('description', weight='B')
        search_query = SearchQuery(q, search_type='websearch')
        return (
            queryset.annotate(
                search_rank=SearchRank(search_vector, search_query),
                search_steps_text=Cast('steps', output_field=TextField()),
            )
            .filter(
                Q(search_rank__gt=0)
                | Q(ingredients__name__icontains=q)
                | Q(search_steps_text__icontains=q)
            )
            .distinct(),
            True,
        )

    return _fallback_recipe_search(queryset, q), False


def get_client_ip(request) -> str:
    """Resolve client IP, trusting forwarded headers only from trusted proxies."""
    remote_addr = str(request.META.get('REMOTE_ADDR') or '').strip()
    forwarded_for = str(request.META.get('HTTP_X_FORWARDED_FOR') or '').strip()
    trusted_proxies = {
        str(ip).strip()
        for ip in getattr(settings, 'TRUSTED_PROXY_IPS', [])
        if str(ip).strip()
    }
    if forwarded_for and remote_addr and remote_addr in trusted_proxies:
        forwarded_client = forwarded_for.split(',')[0].strip()
        if forwarded_client:
            return forwarded_client
    return remote_addr or 'unknown'


def rate_limit_config(scope: str) -> tuple[int, int]:
    """Read rate-limit tuple for a scope from settings with safe defaults."""
    configured = getattr(settings, 'RATE_LIMITS', {})
    scope_config = configured.get(scope, {}) if isinstance(configured, dict) else {}
    try:
        limit = int(scope_config.get('limit', 20))
    except (TypeError, ValueError):
        limit = 20
    try:
        window = int(scope_config.get('window', 60))
    except (TypeError, ValueError):
        window = 60
    return max(limit, 1), max(window, 1)


def _consume_rate_limit_bucket(request, *, scope: str, key: str, actor: str) -> bool:
    """Consume one unit from a concrete rate-limit bucket. Return False when blocked."""
    limit, window = rate_limit_config(scope)
    if cache.add(key, 1, timeout=window):
        return True

    try:
        count = int(cache.incr(key))
    except ValueError:
        cache.set(key, 1, timeout=window)
        count = 1
    allowed = count <= limit
    if not allowed:
        logger.warning(
            'request_id=%s event=rate_limited scope=%s actor=%s ip=%s count=%s limit=%s window=%s',
            getattr(request, 'request_id', '-'),
            scope,
            actor,
            get_client_ip(request),
            count,
            limit,
            window,
        )
    return allowed


def consume_rate_limit(request, scope: str) -> bool:
    """Consume one unit from scope rate limit. Return False when blocked."""
    actor = f'u{request.user.id}' if request.user.is_authenticated else 'anon'
    client_ip = get_client_ip(request)
    key = f'ratelimit:{scope}:{actor}:{client_ip}'
    return _consume_rate_limit_bucket(request, scope=scope, key=key, actor=actor)


def consume_login_account_rate_limit(request, username: str) -> bool:
    """Consume one unit from the per-account login bucket. Return False when blocked."""
    normalized = str(username or '').strip().lower()
    if not normalized:
        return True
    key = f'ratelimit:login:account:{normalized}'
    return _consume_rate_limit_bucket(
        request,
        scope='login_account',
        key=key,
        actor=f'account:{normalized}',
    )
