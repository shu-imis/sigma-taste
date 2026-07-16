"""Recipe detail page handlers."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render

from core.forms import ContentReportForm, ReviewForm
from core.models import ContentReport, Reaction, Recipe, User
from core.services.video import get_recipe_tutorial_video_info

from ...shared.http import build_querystring_excluding
from ...shared.messages import RECIPE_UNAVAILABLE
from ...shared.page_content import (
    build_recipe_detail_hero_badges,
    build_recipe_detail_hero_meta_note,
    build_recipe_detail_hero_meta_tokens,
)
from ...shared.reactions import attach_review_reaction_metadata
from .helpers import (
    DETAIL_REVIEWS_PER_PAGE,
    can_review_content_reports,
    can_view_recipe,
)

VIEWED_RECIPES_SESSION_KEY = 'viewed_recipe_ids'
VIEWED_RECIPES_SESSION_LIMIT = 500


def recipe_detail_page(request, recipe_id):
    recipe = get_object_or_404(Recipe.objects.select_related('author').prefetch_related('ingredients'), id=recipe_id)

    can_view, is_recipe_owner = can_view_recipe(request, recipe)
    if not can_view:
        messages.error(request, RECIPE_UNAVAILABLE)
        return redirect('web-home')

    # Count each recipe once per session so repeat views (including anonymous
    # refreshes) do not inflate the view counter.
    viewed_recipe_ids = request.session.get(VIEWED_RECIPES_SESSION_KEY) or []
    if recipe.id not in viewed_recipe_ids:
        Recipe.objects.filter(id=recipe.id).update(view_count=F('view_count') + 1)
        recipe.view_count += 1
        # Keep only the most recent ids so the session list cannot grow without bound.
        request.session[VIEWED_RECIPES_SESSION_KEY] = [*viewed_recipe_ids, recipe.id][-VIEWED_RECIPES_SESSION_LIMIT:]

    review_page_number = request.GET.get('review_page') or '1'
    review_paginator = Paginator(recipe.reviews.select_related('user'), DETAIL_REVIEWS_PER_PAGE)
    review_page = review_paginator.get_page(review_page_number)
    reviews = list(review_page.object_list)
    viewer_id = request.user.id if request.user.is_authenticated else None
    attach_review_reaction_metadata(reviews, viewer_id)
    viewer_review = None
    if request.user.is_authenticated:
        viewer_review = recipe.reviews.filter(user=request.user).first()
    # Bind the viewer's existing review so the form (including the anonymous
    # checkbox) reflects the current state instead of silently resetting it.
    review_form = ReviewForm(instance=viewer_review)

    can_manage_recipe = request.user.is_authenticated and request.user.has_capability(
        User.CAPABILITY_UPDATE_RECIPE_STATUS
    )
    can_delete_recipe = is_recipe_owner or (
        request.user.is_authenticated and request.user.has_capability(User.CAPABILITY_DELETE_ANY_RECIPE)
    )
    can_moderate_reports = can_review_content_reports(request.user)
    recipe_pending_report_count = 0
    if can_moderate_reports:
        recipe_pending_report_count = ContentReport.objects.filter(
            target_type=ContentReport.TARGET_RECIPE,
            target_id=recipe.id,
            status=ContentReport.STATUS_PENDING,
        ).count()

    return render(
        request,
        'core/pages/recipe/detail.html',
        {
            'recipe': recipe,
            'reviews': reviews,
            'review_page': review_page,
            'review_querystring': build_querystring_excluding(request, 'review_page'),
            'review_form': review_form,
            'is_recipe_owner': is_recipe_owner,
            'can_manage_recipe': can_manage_recipe,
            'can_delete_recipe': can_delete_recipe,
            'can_moderate_reports': can_moderate_reports,
            'recipe_pending_report_count': recipe_pending_report_count,
            'report_reason_choices': ContentReport.REASON_CHOICES,
            'report_form': ContentReportForm(),
            'hero_meta_tokens': build_recipe_detail_hero_meta_tokens(recipe),
            'hero_meta_note': build_recipe_detail_hero_meta_note(recipe),
            'hero_badges': build_recipe_detail_hero_badges(recipe, can_manage_recipe=can_manage_recipe),
            'reaction_emoji_options': Reaction.EMOJI_CHOICES,
            'tutorial_video': get_recipe_tutorial_video_info(recipe),
        },
    )
