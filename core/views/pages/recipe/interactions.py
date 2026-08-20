"""Recipe review and reaction handlers."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from core.forms import ReviewForm
from core.models import Reaction, Recipe, Review

from ...shared.http import consume_rate_limit
from ...shared.messages import (
    REACTION_ADDED,
    REACTION_EMOJI_REQUIRED,
    REACTION_EMOJI_UNSUPPORTED,
    REACTION_RATE_LIMIT,
    REACTION_REMOVED,
    REACTION_UPDATED,
    RECIPE_UNAVAILABLE,
    REVIEW_SELF_REVIEW_NOT_ALLOWED,
    REVIEW_SUBMIT_INVALID_FIELDS,
    REVIEW_SUBMIT_RATE_LIMIT,
    REVIEW_SUBMIT_SUCCESS,
    REVIEW_SUBMIT_UPDATED,
)
from ...shared.rankings import invalidate_ranking_snapshot_cache
from ...shared.reactions import REACTION_EMOJIS
from .helpers import can_view_recipe


@login_required
@require_POST
def add_review_page(request, recipe_id):
    recipe = get_object_or_404(Recipe, id=recipe_id)
    can_view, _ = can_view_recipe(request, recipe)
    if not can_view:
        messages.error(request, RECIPE_UNAVAILABLE)
        return redirect('web-home')

    if recipe.author_id == request.user.id:
        messages.error(request, REVIEW_SELF_REVIEW_NOT_ALLOWED)
        return redirect('web-recipe-detail', recipe_id=recipe.id)

    review_form = ReviewForm(request.POST)
    if not review_form.is_valid():
        messages.error(request, REVIEW_SUBMIT_INVALID_FIELDS)
        return redirect('web-recipe-detail', recipe_id=recipe.id)

    if not consume_rate_limit(request, 'review_submit'):
        messages.error(request, REVIEW_SUBMIT_RATE_LIMIT)
        return redirect('web-recipe-detail', recipe_id=recipe.id)

    review_defaults = {
        'rating': review_form.cleaned_data['rating'],
        'content': review_form.cleaned_data['content'],
        'is_anonymous': review_form.cleaned_data['is_anonymous'],
    }
    _, created = Review.objects.update_or_create(
        recipe=recipe,
        user=request.user,
        defaults=review_defaults,
    )
    invalidate_ranking_snapshot_cache()
    messages.success(request, REVIEW_SUBMIT_SUCCESS if created else REVIEW_SUBMIT_UPDATED)
    return redirect('web-recipe-detail', recipe_id=recipe.id)


@login_required
@require_POST
def add_reaction_page(request, review_id):
    review = get_object_or_404(Review.objects.select_related('recipe'), id=review_id)
    recipe_id = review.recipe_id
    can_view, _ = can_view_recipe(request, review.recipe)
    if not can_view:
        messages.error(request, RECIPE_UNAVAILABLE)
        return redirect('web-home')

    if not consume_rate_limit(request, 'reaction'):
        messages.error(request, REACTION_RATE_LIMIT)
        return redirect('web-recipe-detail', recipe_id=recipe_id)

    emoji = request.POST.get('emoji', '').strip()

    if not emoji:
        messages.error(request, REACTION_EMOJI_REQUIRED)
        return redirect('web-recipe-detail', recipe_id=recipe_id)

    if emoji not in REACTION_EMOJIS:
        messages.error(request, REACTION_EMOJI_UNSUPPORTED)
        return redirect('web-recipe-detail', recipe_id=recipe_id)

    current_reaction = Reaction.objects.filter(review=review, user=request.user).first()
    if current_reaction and current_reaction.emoji == emoji:
        current_reaction.delete()
        messages.info(request, REACTION_REMOVED)
    else:
        # update_or_create resolves concurrent first-time reactions on the
        # unique_review_user constraint instead of surfacing an IntegrityError.
        _, created = Reaction.objects.update_or_create(
            review=review,
            user=request.user,
            defaults={'emoji': emoji},
        )
        messages.success(request, REACTION_ADDED if created else REACTION_UPDATED)

    return redirect('web-recipe-detail', recipe_id=recipe_id)
