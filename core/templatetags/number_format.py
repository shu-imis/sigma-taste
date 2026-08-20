"""Template filters for human-friendly numeric display."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()

_COMPACT_UNITS = ('', 'K', 'M', 'B', 'T', 'P')


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _strip_trailing_zeros(text: str) -> str:
    if '.' not in text:
        return text
    return text.rstrip('0').rstrip('.')


@register.filter(name='compact_number')
def compact_number(value):
    """
    Render numeric values in compact notation (e.g. 1.2K, 3.4M).

    Rules:
    - < 1000: show original value without unnecessary trailing zeros.
    - >= 1000: show compact unit with up to one decimal.
    """
    number = _to_decimal(value)
    if number is None:
        return value

    sign = '-' if number < 0 else ''
    abs_number = -number if number < 0 else number

    if abs_number < 1000:
        if abs_number == abs_number.to_integral_value():
            return f'{sign}{int(abs_number)}'
        return f'{sign}{_strip_trailing_zeros(format(abs_number, 'f'))}'

    unit_index = 0
    scaled = abs_number
    while scaled >= 1000 and unit_index < len(_COMPACT_UNITS) - 1:
        scaled /= Decimal('1000')
        unit_index += 1

    rounded = scaled.quantize(Decimal('0.1'))
    if rounded >= 1000 and unit_index < len(_COMPACT_UNITS) - 1:
        rounded /= Decimal('1000')
        unit_index += 1

    body = format(rounded, '.1f')
    return f'{sign}{_strip_trailing_zeros(body)}{_COMPACT_UNITS[unit_index]}'
