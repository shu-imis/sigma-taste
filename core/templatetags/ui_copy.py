"""Template helpers for consistent UI copy rendering."""

from __future__ import annotations

import re

from django import template

register = template.Library()

_SMALL_TITLE_WORDS = {
    'a',
    'an',
    'and',
    'as',
    'at',
    'but',
    'by',
    'for',
    'in',
    'nor',
    'of',
    'on',
    'or',
    'per',
    'so',
    'the',
    'to',
    'via',
    'yet',
}
_UPPER_TITLE_WORDS = {'ai', 'api', 'css', 'dom', 'html', 'id', 'js', 'ui', 'url'}
_WHITESPACE_RE = re.compile(r'(\s+)')


def _is_wordish_char(char: str) -> bool:
    """Return whether the character belongs to a title-cased token."""
    return char.isalnum() or char in {"'", '’', '&'}


def _split_affixes(token: str) -> tuple[str, str, str]:
    """Split surrounding punctuation from a central word token."""
    start = 0
    end = len(token)

    while start < end and not _is_wordish_char(token[start]):
        start += 1
    while end > start and not _is_wordish_char(token[end - 1]):
        end -= 1

    return token[:start], token[start:end], token[end:]


def _capitalize_word(word: str) -> str:
    """Uppercase the first alphabetic character and lowercase the rest."""
    lowered = word.lower()
    for index, char in enumerate(lowered):
        if char.isalpha():
            return f'{lowered[:index]}{char.upper()}{lowered[index + 1:]}'
    return lowered


def _titlecase_simple_word(word: str, *, is_first: bool, is_last: bool, force_capitalize: bool = False) -> str:
    """Apply title-case rules to a single word without surrounding punctuation."""
    if not any(char.isalpha() for char in word):
        return word

    lowered = word.lower()
    if lowered in _UPPER_TITLE_WORDS:
        return lowered.upper()

    letters_only = ''.join(char for char in word if char.isalpha())
    if letters_only and letters_only.isupper() and len(letters_only) <= 5:
        return word

    if not force_capitalize and lowered in _SMALL_TITLE_WORDS and not is_first and not is_last:
        return lowered

    return _capitalize_word(word)


def _titlecase_core(core: str, *, is_first: bool, is_last: bool) -> str:
    """Apply title-case rules to the core word portion of a token."""
    if '-' not in core and '/' not in core:
        return _titlecase_simple_word(core, is_first=is_first, is_last=is_last)

    pieces = re.split(r'([-/])', core)
    word_piece_indexes = [index for index, piece in enumerate(pieces) if piece not in {'-', '/'}]
    if not word_piece_indexes:
        return core

    first_piece_index = word_piece_indexes[0]
    last_piece_index = word_piece_indexes[-1]
    rendered: list[str] = []
    for index, piece in enumerate(pieces):
        if piece in {'-', '/'}:
            rendered.append(piece)
            continue
        rendered.append(
            _titlecase_simple_word(
                piece,
                is_first=is_first and index == first_piece_index,
                is_last=is_last and index == last_piece_index,
                force_capitalize='-' in core,
            )
        )
    return ''.join(rendered)


def _to_ui_label(value) -> str:
    """Render system-facing UI copy as real uppercase text."""
    return str(value or '').upper()


def to_ui_title(value) -> str:
    """Render structured UI copy in title case while preserving acronyms."""
    text = str(value or '')
    if not text:
        return ''

    tokens = _WHITESPACE_RE.split(text)
    word_indexes = [
        index for index, token in enumerate(tokens) if token and not token.isspace() and any(char.isalpha() for char in token)
    ]
    if not word_indexes:
        return text

    first_word_index = word_indexes[0]
    last_word_index = word_indexes[-1]
    rendered: list[str] = []

    for index, token in enumerate(tokens):
        if not token or token.isspace():
            rendered.append(token)
            continue

        prefix, core, suffix = _split_affixes(token)
        if not core:
            rendered.append(token)
            continue

        rendered.append(
            f'{prefix}{_titlecase_core(core, is_first=index == first_word_index, is_last=index == last_word_index)}{suffix}'
        )

    return ''.join(rendered)


@register.filter(name='ui_label')
def ui_label_filter(value):
    """Allow filters to normalize UI label copy in shared templates."""
    return _to_ui_label(value)


@register.simple_tag(name='ui_label')
def ui_label_tag(value):
    """Allow tags to normalize literal strings and variables alike."""
    return _to_ui_label(value)


@register.filter(name='ui_title')
def ui_title_filter(value):
    """Allow filters to normalize structured UI titles and labels."""
    return to_ui_title(value)


@register.simple_tag(name='ui_title')
def ui_title_tag(value):
    """Allow tags to normalize literal strings and variables alike."""
    return to_ui_title(value)
