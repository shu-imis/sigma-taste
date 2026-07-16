"""Bilibili tutorial video URL parsing and embed helpers."""

import re
from typing import Any
from urllib.parse import parse_qs, urlparse

BILIBILI_HOSTS = {
    'www.bilibili.com',
    'm.bilibili.com',
    'bilibili.com',
    'player.bilibili.com',
}

_BVID_RE = re.compile(r'^BV[0-9A-Za-z]{10,}$')
_AV_RE = re.compile(r'^(?:av)?([0-9]+)$', re.IGNORECASE)


def _clean_host(netloc: str) -> str:
    return str(netloc or '').split(':', 1)[0].strip().lower()


def _normalize_page(raw: str | None) -> int:
    try:
        page = int(str(raw or '').strip() or '1')
    except (TypeError, ValueError):
        return 1
    return page if page > 0 else 1


def _extract_page(query: dict[str, list[str]]) -> int:
    page_values = query.get('p') or query.get('page') or ['1']
    return _normalize_page(page_values[0] if page_values else '1')


def _normalize_bvid(value: str) -> str | None:
    token = str(value or '').strip()
    if len(token) < 3:
        return None
    if token[:2].lower() != 'bv':
        return None
    normalized = 'BV' + token[2:]
    if not _BVID_RE.match(normalized):
        return None
    return normalized


def _normalize_aid(value: str) -> str | None:
    token = str(value or '').strip()
    match = _AV_RE.match(token)
    if not match:
        return None
    return match.group(1)


def is_bilibili_host(url: str) -> bool:
    """Return whether URL host belongs to supported Bilibili domains."""
    try:
        parsed = urlparse(str(url or '').strip())
    except Exception:
        return False
    return _clean_host(parsed.netloc) in BILIBILI_HOSTS


def build_bilibili_embed_url(parsed: dict[str, Any]) -> str:
    """Build a stable Bilibili embed URL from parsed identifiers."""
    page = _normalize_page(parsed.get('page'))
    bvid = str(parsed.get('bvid') or '').strip()
    aid = str(parsed.get('aid') or '').strip()
    if bvid:
        return f'https://player.bilibili.com/player.html?bvid={bvid}&page={page}'
    return f'https://player.bilibili.com/player.html?aid={aid}&page={page}'


def parse_bilibili_video_url(url: str) -> dict[str, Any] | None:
    """Parse a supported Bilibili video URL into canonical source/embed data."""
    raw = str(url or '').strip()
    if not raw:
        return None

    try:
        parsed = urlparse(raw)
    except Exception:
        return None

    if parsed.scheme not in {'http', 'https'}:
        return None

    host = _clean_host(parsed.netloc)
    if host not in BILIBILI_HOSTS:
        return None

    query = parse_qs(parsed.query)
    page = _extract_page(query)
    path = str(parsed.path or '').strip()
    path_parts = [part for part in path.split('/') if part]

    bvid = None
    aid = None

    if path_parts[:1] == ['video'] and len(path_parts) >= 2:
        token = path_parts[1]
        bvid = _normalize_bvid(token)
        if not bvid:
            aid = _normalize_aid(token)
    elif host == 'player.bilibili.com' and path == '/player.html':
        bvid = _normalize_bvid((query.get('bvid') or [''])[0])
        if not bvid:
            aid = _normalize_aid((query.get('aid') or [''])[0])

    if not bvid and not aid:
        return None

    if bvid:
        source_url = f'https://www.bilibili.com/video/{bvid}'
    else:
        source_url = f'https://www.bilibili.com/video/av{aid}'

    if page > 1:
        source_url = f'{source_url}?p={page}'

    parsed_result = {
        'provider': 'bilibili',
        'source_url': source_url,
        'bvid': bvid,
        'aid': aid,
        'page': page,
    }
    parsed_result['embed_url'] = build_bilibili_embed_url(parsed_result)
    return parsed_result


def get_recipe_tutorial_video_info(recipe: Any) -> dict[str, Any] | None:
    """Resolve one recipe tutorial URL into embeddable or external-link display info."""
    source_url = str(getattr(recipe, 'tutorial_video_url', '') or '').strip()
    if not source_url:
        return None

    parsed = parse_bilibili_video_url(source_url)
    if parsed:
        return {
            'provider': 'bilibili',
            'source_url': parsed['source_url'],
            'embed_url': parsed['embed_url'],
            'is_embeddable': True,
        }

    return {
        'provider': 'external',
        'source_url': source_url,
        'embed_url': '',
        'is_embeddable': False,
    }
