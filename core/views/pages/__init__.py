"""Page-level view handlers."""

from .ai import ai_generate_page
from .auth import login_page, logout_page, profile_page, register_page
from .boards import boards_page
from .recipe import (
    add_reaction_page,
    add_review_page,
    create_recipe_page,
    delete_recipe_page,
    home_page,
    recipe_detail_page,
    update_recipe_status_page,
)

__all__ = [
    'ai_generate_page',
    'login_page',
    'logout_page',
    'profile_page',
    'register_page',
    'boards_page',
    'add_reaction_page',
    'add_review_page',
    'create_recipe_page',
    'delete_recipe_page',
    'home_page',
    'recipe_detail_page',
    'update_recipe_status_page',
]
