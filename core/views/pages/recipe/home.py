"""Recipe feed and listing handlers."""

from django.core.paginator import Paginator
from django.db.models import Avg, Count, F
from django.shortcuts import render

from core.models import Recipe

from ...shared.http import apply_recipe_search, build_querystring_excluding
from ...shared.page_content import DISCOVER_HERO_BADGES, build_home_empty_state
from ...shared.panels import build_home_sidebar_panels
from .helpers import (
    HOME_RECIPES_PER_PAGE,
    collect_home_card_tags,
    visible_recipe_queryset_for_request,
)


def home_page(request):
    visible_queryset = visible_recipe_queryset_for_request(request)
    queryset = visible_queryset.select_related('author').annotate(
        avg_rating=Avg('reviews__rating'),
        review_count=Count('reviews', distinct=True),
    )

    q = request.GET.get('q', '').strip()
    cuisine = request.GET.get('cuisine', '').strip()
    flavor = request.GET.get('flavor', '').strip()
    sort = request.GET.get('sort', 'latest')
    used_full_text = False

    if q:
        queryset, used_full_text = apply_recipe_search(queryset, q)
    if cuisine:
        queryset = queryset.filter(cuisine__icontains=cuisine)
    if flavor:
        queryset = queryset.filter(flavor__icontains=flavor)

    if sort == 'rating':
        queryset = queryset.order_by(F('avg_rating').desc(nulls_last=True), '-created_at')
    elif sort == 'hot':
        queryset = queryset.order_by(F('view_count').desc(), F('search_count').desc(), '-created_at')
    else:
        if q and used_full_text:
            queryset = queryset.order_by(F('search_rank').desc(nulls_last=True), '-created_at')
        else:
            queryset = queryset.order_by('-created_at')

    recipe_page_number = request.GET.get('page') or '1'
    recipe_paginator = Paginator(queryset, HOME_RECIPES_PER_PAGE)
    recipe_page = recipe_paginator.get_page(recipe_page_number)
    top_recipes = list(recipe_page.object_list)
    for recipe in top_recipes:
        recipe.home_card_tags = collect_home_card_tags(recipe)
    if q and top_recipes:
        Recipe.objects.filter(id__in=[recipe.id for recipe in top_recipes]).update(search_count=F('search_count') + 1)
    hot_recipes = Recipe.objects.filter(status=Recipe.STATUS_PUBLISHED).only(
        'id',
        'title',
        'view_count',
        'created_at',
    ).order_by(
        F('view_count').desc(),
        '-created_at',
    )[:5]

    context = {
        'recipes': top_recipes,
        'recipe_page': recipe_page,
        'hot_recipes': hot_recipes,
        'q': q,
        'cuisine': cuisine,
        'flavor': flavor,
        'sort': sort,
        'hero_badges': DISCOVER_HERO_BADGES,
        'home_empty_state': build_home_empty_state(),
        'home_sidebar_panels': build_home_sidebar_panels(hot_recipes),
        'feed_querystring': build_querystring_excluding(request, 'page'),
    }
    return render(request, 'core/pages/recipe/home.html', context)
