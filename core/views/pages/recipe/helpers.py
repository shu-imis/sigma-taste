"""Shared helpers for recipe page handlers."""

from django.db.models import Q

from core.models import Recipe, User
from core.services.recipe import dedupe_casefolded

HOME_RECIPES_PER_PAGE = 12
DETAIL_REVIEWS_PER_PAGE = 8


def collect_home_card_tags(recipe: Recipe) -> list[str]:
    """Build ordered, deduplicated home-card tags."""
    ordered_tags: list[str] = []
    if recipe.status != Recipe.STATUS_PUBLISHED:
        ordered_tags.append(f'Status: {recipe.get_status_display()}')
    if recipe.is_ai_generated:
        ordered_tags.append('AI-assisted')
    ordered_tags.extend(recipe.flavor_tags)

    cleaned_tags = [str(tag).strip() for tag in ordered_tags]
    return dedupe_casefolded(cleaned_tags)


def can_view_recipe(request, recipe: Recipe) -> tuple[bool, bool]:
    """Return (can_view, is_owner) for the current request and recipe."""
    is_recipe_owner = request.user.is_authenticated and recipe.author_id == request.user.id
    can_view_non_public = request.user.is_authenticated and request.user.has_capability(
        User.CAPABILITY_VIEW_NON_PUBLIC_RECIPE
    )
    can_view = recipe.status == Recipe.STATUS_PUBLISHED or is_recipe_owner or can_view_non_public
    return can_view, is_recipe_owner


def can_review_content_reports(user) -> bool:
    """Return whether the user may work the content report queue."""
    return bool(user.is_authenticated and user.has_capability(User.CAPABILITY_REVIEW_CONTENT_REPORTS))


def visible_recipe_queryset_for_request(request):
    """Return recipe queryset scoped to viewer visibility permissions."""
    queryset = Recipe.objects.all()
    if not request.user.is_authenticated:
        return queryset.filter(status=Recipe.STATUS_PUBLISHED)
    if request.user.has_capability(User.CAPABILITY_VIEW_NON_PUBLIC_RECIPE):
        return queryset
    return queryset.filter(Q(status=Recipe.STATUS_PUBLISHED) | Q(author_id=request.user.id))
