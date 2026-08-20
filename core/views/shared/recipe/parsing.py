"""Parsing helpers for recipe form inputs."""

from core.services.recipe import clamp_ingredient_row


def parse_steps(text: str) -> list[str]:
    """Convert multiline input into a cleaned recipe-step list."""
    steps: list[str] = []
    for line in text.splitlines():
        line = line.strip().lstrip('-').strip().lstrip('0123456789.').strip()
        if line:
            steps.append(line)
    return steps


def parse_ingredients(text: str) -> list[dict[str, str]]:
    """Parse CSV-like ingredient lines into normalized ingredient rows."""
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split(',')]
        name = parts[0]
        if not name:
            continue
        rows.append(
            clamp_ingredient_row(
                {
                    'name': name,
                    'quantity': parts[1] if len(parts) > 1 else '',
                    'unit': parts[2] if len(parts) > 2 else '',
                    'alternative': parts[3] if len(parts) > 3 else '',
                }
            )
        )
    return rows
