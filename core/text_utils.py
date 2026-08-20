"""Shared text inspection helpers."""

import re
from typing import Any

CJK_CHAR_RE = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]')


def contains_cjk_text(text: str) -> bool:
    """Return whether the provided text contains CJK ideographs."""
    return bool(CJK_CHAR_RE.search((text or '').strip()))


def contains_cjk(value: Any) -> bool:
    """Detect whether a (possibly nested) payload contains CJK characters."""
    if isinstance(value, str):
        return bool(CJK_CHAR_RE.search(value))
    if isinstance(value, dict):
        return any(contains_cjk(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_cjk(item) for item in value)
    return False
