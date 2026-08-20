"""Template filters for stable avatar glyph display."""

from __future__ import annotations

from django import template

from core.text_utils import CJK_CHAR_RE

register = template.Library()


def _first_readable_char(value) -> str:
    """Return the first readable alphanumeric character for avatar display."""
    text = str(value or '').strip()
    for char in text:
        if char.isalnum():
            return char
    return '?'


@register.filter(name='avatar_glyph')
def avatar_glyph(value):
    """Render a single avatar glyph from a username or label source."""
    glyph = _first_readable_char(value)
    if glyph.isascii() and glyph.isalpha():
        return glyph.upper()
    return glyph


@register.filter(name='avatar_variant')
def avatar_variant(value):
    """Resolve a styling variant for avatar glyph typography."""
    glyph = _first_readable_char(value)
    if glyph == '?':
        return 'fallback'
    if CJK_CHAR_RE.search(glyph):
        return 'cjk'
    if glyph.isdigit():
        return 'numeric'
    return 'default'
