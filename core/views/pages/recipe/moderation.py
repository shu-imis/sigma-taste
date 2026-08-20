"""Recipe moderation handlers."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from core.models import Recipe, User

from ...shared.messages import (
    RECIPE_INVALID_STATUS,
    RECIPE_PERMISSION_DELETE,
    RECIPE_PERMISSION_UPDATE,
    recipe_removed_message,
    recipe_status_already_message,
    recipe_status_updated_message,
)
from ...shared.rankings import invalidate_ranking_snapshot_cache


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
