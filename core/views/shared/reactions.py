"""Reaction metadata helpers shared by recipe detail views."""

from django.db.models import Count

from core.models import Reaction, Review

REACTION_EMOJIS: tuple[str, ...] = tuple(choice[0] for choice in Reaction.EMOJI_CHOICES)

__all__ = [
    'REACTION_EMOJIS',
    'attach_review_reaction_metadata',
]


def attach_review_reaction_metadata(reviews: list[Review], viewer_id: int | None = None) -> None:
    """Attach reaction summary and viewer selection onto each review object."""
    review_ids = [review.id for review in reviews if review.id]
    if not review_ids:
        return

    reaction_rows = (
        Reaction.objects.filter(review_id__in=review_ids, emoji__in=REACTION_EMOJIS)
        .values('review_id', 'emoji')
        .annotate(total=Count('id'))
    )

    reaction_map: dict[int, dict[str, int]] = {}
    for row in reaction_rows:
        review_id = int(row['review_id'])
        emoji = str(row['emoji'])
        total = int(row['total'])
        reaction_map.setdefault(review_id, {})[emoji] = total

    viewer_map: dict[int, str] = {}
    if viewer_id:
        viewer_rows = (
            Reaction.objects.filter(review_id__in=review_ids, user_id=viewer_id, emoji__in=REACTION_EMOJIS)
            .order_by('review_id', '-created_at', '-id')
            .values('review_id', 'emoji')
        )
        for row in viewer_rows:
            review_id = int(row['review_id'])
            if review_id not in viewer_map:
                viewer_map[review_id] = str(row['emoji'])

    for review in reviews:
        counts = reaction_map.get(review.id, {})
        review.reaction_summary = [(emoji, counts.get(emoji, 0)) for emoji in REACTION_EMOJIS if counts.get(emoji, 0) > 0]
        review.viewer_reaction = viewer_map.get(review.id, '')
