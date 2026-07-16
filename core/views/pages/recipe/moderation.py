"""Recipe moderation handlers."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import ContentReport, Recipe, Review, User

from ...shared.messages import (
    RECIPE_INVALID_STATUS,
    RECIPE_PERMISSION_DELETE,
    RECIPE_PERMISSION_UPDATE,
    REVIEW_ALREADY_REMOVED,
    REVIEW_DELETE_REPORT_RESOLUTION_NOTE,
    REVIEW_PERMISSION_DELETE,
    REVIEW_REMOVED,
    recipe_removed_message,
    recipe_status_already_message,
    recipe_status_updated_message,
)
from ...shared.rankings import invalidate_ranking_snapshot_cache
from .helpers import can_review_content_reports


@login_required
@require_POST
def update_recipe_status_page(request, recipe_id):
    if not request.user.has_capability(User.CAPABILITY_UPDATE_RECIPE_STATUS):
        messages.error(request, RECIPE_PERMISSION_UPDATE)
        return redirect('web-recipe-detail', recipe_id=recipe_id)

    recipe = get_object_or_404(Recipe, id=recipe_id)
    status = (request.POST.get('status') or '').strip()
    valid_statuses = {choice[0] for choice in Recipe.STATUS_CHOICES}
    if status not in valid_statuses:
        messages.error(request, RECIPE_INVALID_STATUS)
        return redirect('web-recipe-detail', recipe_id=recipe.id)

    if recipe.status == status:
        messages.info(request, recipe_status_already_message(recipe.get_status_display()))
        return redirect('web-recipe-detail', recipe_id=recipe.id)

    recipe.status = status
    recipe.save(update_fields=['status', 'updated_at'])
    invalidate_ranking_snapshot_cache()
    messages.success(request, recipe_status_updated_message(recipe.get_status_display()))
    return redirect('web-recipe-detail', recipe_id=recipe.id)


@login_required
@require_POST
def delete_recipe_page(request, recipe_id):
    recipe = get_object_or_404(Recipe, id=recipe_id)
    can_delete_recipe = recipe.author_id == request.user.id or request.user.has_capability(
        User.CAPABILITY_DELETE_ANY_RECIPE
    )
    if not can_delete_recipe:
        messages.error(request, RECIPE_PERMISSION_DELETE)
        return redirect('web-recipe-detail', recipe_id=recipe.id)

    recipe_title = recipe.title
    recipe.delete()
    invalidate_ranking_snapshot_cache()
    messages.success(request, recipe_removed_message(recipe_title))
    return redirect('web-home')


@login_required
@require_POST
def delete_review_page(request, review_id):
    if not can_review_content_reports(request.user):
        messages.error(request, REVIEW_PERMISSION_DELETE)
        return redirect('web-home')

    review = Review.objects.filter(id=review_id).first()
    if review is None:
        messages.info(request, REVIEW_ALREADY_REMOVED)
        return redirect('web-report-queue')

    now = timezone.now()
    with transaction.atomic():
        review.delete()
        # Removing the note is itself the moderation decision: resolve any
        # pending reports pointing at it instead of leaving orphaned rows.
        ContentReport.objects.filter(
            target_type=ContentReport.TARGET_REVIEW,
            target_id=review_id,
            status=ContentReport.STATUS_PENDING,
        ).update(
            status=ContentReport.STATUS_RESOLVED,
            reviewer=request.user,
            reviewed_at=now,
            resolution_note=REVIEW_DELETE_REPORT_RESOLUTION_NOTE,
            updated_at=now,
        )
    invalidate_ranking_snapshot_cache()
    messages.success(request, REVIEW_REMOVED)
    return redirect('web-report-queue')
