"""Boards page handlers."""

from django.shortcuts import render

from ..shared.page_content import BOARDS_HERO_BADGES, build_boards_empty_state
from ..shared.rankings import build_ranking_snapshot_record, clean_ranking_filters

__all__ = ['boards_page']


def boards_page(request):
    rank_type, window = clean_ranking_filters(
        request.GET.get('type', 'red'),
        request.GET.get('window', 'week'),
    )
    ranking = build_ranking_snapshot_record(rank_type, window)
    return render(
        request,
        'core/pages/boards/boards.html',
        {
            'ranking': ranking,
            'rank_type': rank_type,
            'window': window,
            'hero_badges': BOARDS_HERO_BADGES,
            'boards_empty_state': build_boards_empty_state(ranking),
        },
    )
