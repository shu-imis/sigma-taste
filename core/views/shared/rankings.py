"""Ranking helpers and template-facing ranking snapshot object."""

from typing import Any

from core.services.rankings import (
    RANKING_TYPES,
    RANKING_WINDOWS,
    build_snapshot,
    invalidate_cache,
)

VALID_RANK_TYPES = set(RANKING_TYPES)
VALID_RANK_WINDOWS = set(RANKING_WINDOWS)
RANK_TYPE_LABELS = {
    'red': 'Recipes people revisit',
    'black': 'Recipes under discussion',
    'ai': 'AI drafts to watch',
}
RANK_WINDOW_LABELS = {
    'day': 'Past 24 hours',
    'week': 'Past 7 days',
    'month': 'Past 30 days',
}

__all__ = [
    'build_ranking_snapshot_record',
    'clean_ranking_filters',
    'invalidate_ranking_snapshot_cache',
]


class RankingSnapshot:
    """Template-facing ranking view model backed by cache data."""

    def __init__(self, rank_type: str, window: str, data: list[dict[str, Any]], generated_at):
        self.type = rank_type
        self.window = window
        self.data = data
        self.generated_at = generated_at

    def get_type_display(self) -> str:
        return RANK_TYPE_LABELS.get(self.type, self.type)

    def get_window_display(self) -> str:
        return RANK_WINDOW_LABELS.get(self.window, self.window)


def clean_ranking_filters(rank_type: str, window: str) -> tuple[str, str]:
    """Keep ranking filters within supported enum values."""
    clean_type = rank_type if rank_type in VALID_RANK_TYPES else 'red'
    clean_window = window if window in VALID_RANK_WINDOWS else 'week'
    return clean_type, clean_window


def build_ranking_snapshot_record(rank_type: str, window: str) -> RankingSnapshot:
    """Build a lightweight ranking snapshot from short-lived cache."""
    snapshot = build_snapshot(rank_type, window)
    return RankingSnapshot(rank_type=rank_type, window=window, data=snapshot['data'], generated_at=snapshot['generated_at'])


def invalidate_ranking_snapshot_cache() -> None:
    """Invalidate cached ranking snapshots after write operations."""
    invalidate_cache()
