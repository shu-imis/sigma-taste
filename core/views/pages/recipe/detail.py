"""Recipe detail page handlers."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render

from core.forms import ReviewForm
from core.models import Recipe, User

from ...shared.http import build_querystring_excluding
from ...shared.messages import RECIPE_UNAVAILABLE
from ...shared.page_content import (
    build_recipe_detail_hero_badges,
    build_recipe_detail_hero_meta_note,
    build_recipe_detail_hero_meta_tokens,
)
from ...shared.reactions import REACTION_EMOJIS, attach_review_reaction_metadata
from .helpers import DETAIL_REVIEWS_PER_PAGE, can_view_recipe


def recipe_detail_page(request, recipe_id):
    recipe = get_object_or_404(Recipe.objects.select_related('author').prefetch_related('ingredients'), id=recipe_id)

    can_view, is_recipe_owner = can_view_recipe(request, recipe)
    if not can_view:
        messages.error(request, RECIPE_UNAVAILABLE)
        return redirect('web-home')

    Recipe.objects.filter(id=recipe.id).update(view_count=F('view_count') + 1)
    recipe.view_count += 1

    review_page_number = request.GET.get('review_page') or '1'
    review_paginator = Paginator(recipe.reviews.select_related('user'), DETAIL_REVIEWS_PER_PAGE)
    review_page = review_paginator.get_page(review_page_number)
    reviews = list(review_page.object_list)
    viewer_id = request.user.id if request.user.is_authenticated else None
    attach_review_reaction_metadata(reviews, viewer_id)
    review_form = ReviewForm()

    can_manage_recipe = request.user.is_authenticated and request.user.has_capability(
        User.CAPABILITY_UPDATE_RECIPE_STATUS
    )
    can_delete_recipe = is_recipe_owner or (
        request.user.is_authenticated and request.user.has_capability(User.CAPABILITY_DELETE_ANY_RECIPE)
    )

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
            'hero_meta_tokens': build_recipe_detail_hero_meta_tokens(recipe),
            'hero_meta_note': build_recipe_detail_hero_meta_note(recipe),
            'hero_badges': build_recipe_detail_hero_badges(recipe, can_manage_recipe=can_manage_recipe),
            'reaction_emoji_options': REACTION_EMOJIS,
        },
    )
