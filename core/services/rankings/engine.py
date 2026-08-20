"""Simplified ranking calculation logic for community board pages."""

import math
from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.utils import timezone

from ...models import Recipe

RED_SCORE_WEIGHTS = {
    'rating': 12.0,
    'reviews': 8.0,
    'positive': 3.0,
}
BLACK_SCORE_WEIGHTS = {
    'concern': 10.0,
    'reviews': 7.0,
}
AI_SCORE_WEIGHTS = {
    'rating': 10.0,
    'positive': 6.0,
    'reviews': 4.0,
}
HEAT_VIEW_WEIGHT = 1.0
HEAT_SEARCH_WEIGHT = 2.0
HEAT_LOG_SCALE = 6.0
STALE_HEAT_MULTIPLIER = 0.35
RED_SCORE_REVIEW_CAP = 30.0


def _window_start(window: str):
    """Return the inclusive start timestamp for a ranking window."""
    now = timezone.now()
    if window == 'day':
        return now - timedelta(days=1)
    if window == 'month':
        return now - timedelta(days=30)
    return now - timedelta(days=7)


def _windowed_queryset(rank_type: str, *, start_time):
    """Prepare one queryset with the windowed review signals needed by the boards."""
    queryset = Recipe.objects.filter(status=Recipe.STATUS_PUBLISHED)
    if rank_type == 'ai':
        queryset = queryset.filter(is_ai_generated=True)
    return queryset.only(
        'id',
        'title',
        'created_at',
        'view_count',
        'search_count',
    ).annotate(
        avg_rating_window=Avg('reviews__rating', filter=Q(reviews__created_at__gte=start_time)),
        review_count_window=Count('reviews', filter=Q(reviews__created_at__gte=start_time), distinct=True),
        positive_review_count_window=Count(
            'reviews',
            filter=Q(reviews__created_at__gte=start_time, reviews__rating__gte=4),
            distinct=True,
        ),
    ).order_by('-created_at')


def _heat_points(recipe, *, start_time) -> float:
    """Use the recipe's accumulated public activity as a lightweight heat signal."""
    weighted_activity = max(
        float(recipe.view_count or 0) * HEAT_VIEW_WEIGHT
        + float(recipe.search_count or 0) * HEAT_SEARCH_WEIGHT,
        0.0,
    )
    if weighted_activity <= 0:
        return 0.0
    multiplier = 1.0 if recipe.created_at >= start_time else STALE_HEAT_MULTIPLIER
    return math.log1p(weighted_activity) * HEAT_LOG_SCALE * multiplier


def _red_score(*, avg_rating: float, review_count: int, positive_count: int, heat_points: float) -> float:
    volume_ratio = min(float(review_count), RED_SCORE_REVIEW_CAP) / RED_SCORE_REVIEW_CAP
    return (
        avg_rating * RED_SCORE_WEIGHTS['rating']
        + volume_ratio * RED_SCORE_WEIGHTS['reviews']
        + positive_count * RED_SCORE_WEIGHTS['positive']
        + heat_points
    )


def _black_score(*, avg_rating: float, review_count: int, heat_points: float) -> float:
    concern_points = max(0.0, 5.5 - avg_rating) * BLACK_SCORE_WEIGHTS['concern'] if review_count else 0.0
    return concern_points + review_count * BLACK_SCORE_WEIGHTS['reviews'] + heat_points


def _ai_score(*, avg_rating: float, review_count: int, positive_count: int, heat_points: float) -> float:
    return (
        avg_rating * AI_SCORE_WEIGHTS['rating']
        + positive_count * AI_SCORE_WEIGHTS['positive']
        + review_count * AI_SCORE_WEIGHTS['reviews']
        + heat_points
    )


def calculate_rankings(rank_type: str, window: str):
    """Compute ranking rows by type and time window using fixed, readable heuristics."""
    start_time = _window_start(window)
    ranking_rows = []

    for recipe in _windowed_queryset(rank_type, start_time=start_time).iterator():
        avg_rating = float(recipe.avg_rating_window or 0.0)
        review_count = int(recipe.review_count_window or 0)
        positive_count = int(recipe.positive_review_count_window or 0)
        heat_points = _heat_points(recipe, start_time=start_time)

        if rank_type == 'black' and review_count < 1:
            # The black board flags poorly-reviewed recipes; heat alone is not a signal.
            continue

        if rank_type == 'black':
            score = _black_score(
                avg_rating=avg_rating,
                review_count=review_count,
                heat_points=heat_points,
            )
        elif rank_type == 'ai':
            score = _ai_score(
                avg_rating=avg_rating,
                review_count=review_count,
                positive_count=positive_count,
                heat_points=heat_points,
            )
        else:
            score = _red_score(
                avg_rating=avg_rating,
                review_count=review_count,
                positive_count=positive_count,
                heat_points=heat_points,
            )

        ranking_rows.append(
            {
                'recipe_id': recipe.id,
                'title': recipe.title,
                'score': round(max(score, 0.0), 2),
                'avg_rating': round(avg_rating, 2),
                'review_count': review_count,
            }
        )

    ranking_rows.sort(key=lambda row: row['score'], reverse=True)
    return ranking_rows[:10]
