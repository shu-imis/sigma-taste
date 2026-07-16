"""Recipe-related page handlers."""

from .create import create_recipe_page
from .detail import recipe_detail_page
from .home import home_page
from .interactions import add_reaction_page, add_review_page
from .moderation import (
    delete_recipe_page,
    delete_review_page,
    update_recipe_status_page,
)
from .reports import (
    report_queue_page,
    report_recipe_page,
    report_review_page,
    resolve_report_page,
)

__all__ = [
    'add_reaction_page',
    'add_review_page',
    'create_recipe_page',
    'delete_recipe_page',
    'delete_review_page',
    'home_page',
    'recipe_detail_page',
    'report_queue_page',
    'report_recipe_page',
    'report_review_page',
    'resolve_report_page',
    'update_recipe_status_page',
]
