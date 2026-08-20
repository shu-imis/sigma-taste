"""Website view exports."""

from .pages import (
    add_reaction_page,
    add_review_page,
    ai_generate_page,
    boards_page,
    create_recipe_page,
    delete_recipe_page,
    home_page,
    login_page,
    logout_page,
    profile_page,
    recipe_detail_page,
    register_page,
    update_recipe_status_page,
)

__all__ = [
    'add_reaction_page',
    'add_review_page',
    'ai_generate_page',
    'create_recipe_page',
    'delete_recipe_page',
    'home_page',
    'login_page',
    'logout_page',
    'profile_page',
    'boards_page',
    'recipe_detail_page',
    'register_page',
    'update_recipe_status_page',
]
