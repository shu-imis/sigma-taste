"""User-facing message strings shared by page-level handlers."""

AI_PUBLISH_RATE_LIMIT = 'Too many publish attempts. Please give it a moment and try again.'
AI_PUBLISH_DRAFT_EXPIRED = 'That draft is no longer available. Generate it again when you are ready.'
AI_PUBLISH_SUCCESS = 'Your AI draft has been saved to your recipe box.'
AI_GENERATE_RATE_LIMIT = 'Too many AI generation requests. Please give it a moment and try again.'
AI_GENERATE_DUPLICATE_IN_PROGRESS = 'Your previous AI generation is still running. Please give it a moment.'
AI_GENERATE_DUPLICATE_REUSED = 'We reopened the most recent AI draft for this request.'
AI_MODEL_UNAVAILABLE = 'Choose an available local model to continue.'
AI_MODEL_REQUIRED = 'Choose a model before continuing.'
AI_MODEL_SET_SUCCESS = 'This model is ready to use.'
AI_GENERATE_UNAVAILABLE = 'AI recipe generation is unavailable right now. Please try again shortly.'

AUTH_REGISTER_SUCCESS = 'Welcome. Your account is ready.'
AUTH_REGISTER_RATE_LIMIT = 'Too many account creation attempts. Please give it a moment and try again.'
AUTH_LOGIN_RATE_LIMIT = 'Too many sign-in attempts. Please give it a moment and try again.'
AUTH_LOGIN_SUCCESS = 'Welcome back. Everything you saved is here.'
AUTH_LOGOUT_INFO = 'You have signed out for now.'
PROFILE_SAVE_SUCCESS = 'Your profile has been updated.'

REVIEW_SUBMIT_RATE_LIMIT = 'Too many review submissions. Please give it a moment and try again.'
REVIEW_SELF_REVIEW_NOT_ALLOWED = 'You cannot review your own recipe.'
REVIEW_SUBMIT_INVALID_FIELDS = 'Complete the review before sharing it.'
REVIEW_SUBMIT_SUCCESS = 'Thank you. Your note is now part of the page.'
REVIEW_SUBMIT_UPDATED = 'Your earlier review has been updated.'

REACTION_RATE_LIMIT = 'Too many reaction requests. Please give it a moment and try again.'
REACTION_EMOJI_REQUIRED = 'Choose an emoji before responding.'
REACTION_EMOJI_UNSUPPORTED = 'That reaction is not available.'
REACTION_REMOVED = 'Your reaction has been removed.'
REACTION_UPDATED = 'Your reaction has been updated.'
REACTION_ADDED = 'Your reaction has been added.'

RECIPE_UNAVAILABLE = 'This recipe is unavailable right now.'
RECIPE_PERMISSION_UPDATE = "You do not have permission to change this recipe's visibility."
RECIPE_INVALID_STATUS = 'That status is not available for this recipe.'
RECIPE_PERMISSION_DELETE = 'You do not have permission to remove this recipe.'

RECIPE_CREATE_RATE_LIMIT = 'Too many recipe publish attempts. Please give it a moment and try again.'
RECIPE_CREATE_STEPS_REQUIRED = 'Add at least one step so another cook can follow along.'
RECIPE_CREATE_INGREDIENTS_REQUIRED = 'Add at least one ingredient so another cook can cook from it.'
RECIPE_CREATE_DUPLICATE_IN_PROGRESS = 'Your previous publish is still being processed. Please give it a moment.'
RECIPE_CREATE_DUPLICATE_REDIRECT = 'This recipe was already shared. We reopened the existing page.'
RECIPE_CREATE_DRAFT_READY = 'Your AI draft is ready to refine in Recipe Studio.'
RECIPE_CREATE_SUCCESS_MANUAL = 'Your recipe has been shared.'


__all__ = [
    'AI_GENERATE_DUPLICATE_IN_PROGRESS',
    'AI_GENERATE_DUPLICATE_REUSED',
    'AI_GENERATE_RATE_LIMIT',
    'AI_GENERATE_UNAVAILABLE',
    'AI_MODEL_REQUIRED',
    'AI_MODEL_SET_SUCCESS',
    'AI_MODEL_UNAVAILABLE',
    'AI_PUBLISH_DRAFT_EXPIRED',
    'AI_PUBLISH_RATE_LIMIT',
    'AI_PUBLISH_SUCCESS',
    'AUTH_LOGIN_RATE_LIMIT',
    'AUTH_LOGIN_SUCCESS',
    'AUTH_LOGOUT_INFO',
    'AUTH_REGISTER_RATE_LIMIT',
    'AUTH_REGISTER_SUCCESS',
    'PROFILE_SAVE_SUCCESS',
    'REACTION_ADDED',
    'REACTION_EMOJI_REQUIRED',
    'REACTION_EMOJI_UNSUPPORTED',
    'REACTION_RATE_LIMIT',
    'REACTION_REMOVED',
    'REACTION_UPDATED',
    'RECIPE_CREATE_DUPLICATE_IN_PROGRESS',
    'RECIPE_CREATE_DUPLICATE_REDIRECT',
    'RECIPE_CREATE_DRAFT_READY',
    'RECIPE_CREATE_INGREDIENTS_REQUIRED',
    'RECIPE_CREATE_RATE_LIMIT',
    'RECIPE_CREATE_STEPS_REQUIRED',
    'RECIPE_CREATE_SUCCESS_MANUAL',
    'RECIPE_INVALID_STATUS',
    'RECIPE_PERMISSION_DELETE',
    'RECIPE_PERMISSION_UPDATE',
    'RECIPE_UNAVAILABLE',
    'REVIEW_SELF_REVIEW_NOT_ALLOWED',
    'REVIEW_SUBMIT_INVALID_FIELDS',
    'REVIEW_SUBMIT_RATE_LIMIT',
    'REVIEW_SUBMIT_SUCCESS',
    'REVIEW_SUBMIT_UPDATED',
    'recipe_removed_message',
    'recipe_status_already_message',
    'recipe_status_updated_message',
]


def recipe_status_already_message(status_display: str) -> str:
    """Build info message when target recipe status is unchanged."""
    return f'This recipe is already marked as {status_display}.'


def recipe_status_updated_message(status_display: str) -> str:
    """Build success message after recipe status update."""
    return f'This recipe is now marked as {status_display}.'


def recipe_removed_message(recipe_title: str) -> str:
    """Build success message after recipe deletion."""
    return f'This recipe has been removed: {recipe_title}.'
