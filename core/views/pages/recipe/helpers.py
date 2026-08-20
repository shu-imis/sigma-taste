"""Shared helpers for recipe page handlers."""

from django.db.models import Q

from core.models import Recipe, User

HOME_RECIPES_PER_PAGE = 12
DETAIL_REVIEWS_PER_PAGE = 8


def collect_home_card_tags(recipe: Recipe) -> list[str]:
    """Build ordered, deduplicated home-card tags."""
    ordered_tags: list[str] = []
    if recipe.status != Recipe.STATUS_PUBLISHED:
        ordered_tags.append(f'Status: {recipe.get_status_display()}')
    if recipe.is_ai_generated:
        ordered_tags.append('AI assisted')
    ordered_tags.extend(recipe.flavor_tags)

    deduplicated: list[str] = []
    seen = set()
    for tag in ordered_tags:
        cleaned = str(tag).strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(cleaned)
    return deduplicated


def can_view_recipe(request, recipe: Recipe) -> tuple[bool, bool]:
    """Return (can_view, is_owner) for the current request and recipe."""
    is_recipe_owner = request.user.is_authenticated and recipe.author_id == request.user.id
    can_view_non_public = request.user.is_authenticated and request.user.has_capability(
        User.CAPABILITY_VIEW_NON_PUBLIC_RECIPE
    )
    can_view = recipe.status == Recipe.STATUS_PUBLISHED or is_recipe_owner or can_view_non_public
    return can_view, is_recipe_owner


def visible_recipe_queryset_for_request(request):
    """Return recipe queryset scoped to viewer visibility permissions."""
    queryset = Recipe.objects.all()
    if not request.user.is_authenticated:
        return queryset.filter(status=Recipe.STATUS_PUBLISHED)
    if request.user.has_capability(User.CAPABILITY_VIEW_NON_PUBLIC_RECIPE):
        return queryset
    return queryset.filter(Q(status=Recipe.STATUS_PUBLISHED) | Q(author_id=request.user.id))
