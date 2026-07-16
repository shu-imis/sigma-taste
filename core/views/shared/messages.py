"""User-facing message strings shared by page-level handlers."""

__all__ = [
    'AI_GENERATE_DUPLICATE_IN_PROGRESS',
    'AI_GENERATE_DUPLICATE_REUSED',
    'AI_GENERATE_RATE_LIMIT',
    'AI_GENERATE_UNAVAILABLE',
    'AI_MODEL_REQUIRED',
    'AI_MODEL_SET_RATE_LIMIT',
    'AI_MODEL_SET_SUCCESS',
    'AI_MODEL_UNAVAILABLE',
    'AI_PUBLISH_DRAFT_EXPIRED',
    'AI_PUBLISH_RATE_LIMIT',
    'AI_PUBLISH_SAVE_FAILED',
    'AI_PUBLISH_SUCCESS',
    'AUTH_LOGIN_RATE_LIMIT',
    'AUTH_LOGIN_SUCCESS',
    'AUTH_LOGOUT_INFO',
    'AUTH_REGISTER_CONFLICT',
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
    'RECIPE_CREATE_SUCCESS',
    'RECIPE_INVALID_STATUS',
    'RECIPE_PERMISSION_DELETE',
    'RECIPE_PERMISSION_UPDATE',
    'RECIPE_UNAVAILABLE',
    'REPORT_ALREADY_OPEN',
    'REPORT_ALREADY_REVIEWED',
    'REPORT_QUEUE_PERMISSION',
    'REPORT_RESOLVE_INVALID',
    'REPORT_RESOLVE_RATE_LIMIT',
    'REPORT_SELF_REPORT_NOT_ALLOWED',
    'REPORT_STATUS_DISMISSED',
    'REPORT_STATUS_RESOLVED',
    'REPORT_SUBMIT_INVALID',
    'REPORT_SUBMIT_RATE_LIMIT',
    'REPORT_SUBMIT_SUCCESS',
    'REVIEW_ALREADY_REMOVED',
    'REVIEW_DELETE_REPORT_RESOLUTION_NOTE',
    'REVIEW_PERMISSION_DELETE',
    'REVIEW_REMOVED',
    'REVIEW_SELF_REVIEW_NOT_ALLOWED',
    'REVIEW_SUBMIT_INVALID_FIELDS',
    'REVIEW_SUBMIT_RATE_LIMIT',
    'REVIEW_SUBMIT_SUCCESS',
    'REVIEW_SUBMIT_UPDATED',
    'recipe_removed_message',
    'recipe_status_already_message',
    'recipe_status_updated_message',
]

AI_PUBLISH_RATE_LIMIT = 'Too many publish attempts. Please give it a moment and try again.'
AI_PUBLISH_DRAFT_EXPIRED = 'That draft is no longer available. Generate it again when you are ready.'
AI_PUBLISH_SUCCESS = 'Your AI draft has been saved to your recipe box.'
AI_PUBLISH_SAVE_FAILED = 'We could not save that recipe right now. Your draft is still here. Try publishing it again.'
AI_GENERATE_RATE_LIMIT = 'Too many AI generation requests. Please give it a moment and try again.'
AI_GENERATE_DUPLICATE_IN_PROGRESS = 'Your previous AI generation is still running. Please give it a moment.'
AI_GENERATE_DUPLICATE_REUSED = 'We reopened the most recent AI draft for this request.'
AI_MODEL_UNAVAILABLE = 'Choose an available local model to continue.'
AI_MODEL_REQUIRED = 'Choose a model before continuing.'
AI_MODEL_SET_SUCCESS = 'Your model is ready when you are.'
AI_MODEL_SET_RATE_LIMIT = 'Too many model updates. Please give it a moment and try again.'
AI_GENERATE_UNAVAILABLE = 'AI recipe generation is unavailable right now. Please try again shortly.'

AUTH_REGISTER_SUCCESS = 'Welcome. Your account is ready.'
AUTH_REGISTER_CONFLICT = 'An account with those details already exists. Try signing in instead.'
AUTH_REGISTER_RATE_LIMIT = 'Too many account creation attempts. Please give it a moment and try again.'
AUTH_LOGIN_RATE_LIMIT = 'Too many sign-in attempts. Please give it a moment and try again.'
AUTH_LOGIN_SUCCESS = 'Welcome back. Everything you saved is here.'
AUTH_LOGOUT_INFO = 'You have signed out for now.'
PROFILE_SAVE_SUCCESS = 'Your profile has been updated.'

REVIEW_SUBMIT_RATE_LIMIT = 'Too many note submissions. Please give it a moment and try again.'
REVIEW_SELF_REVIEW_NOT_ALLOWED = 'You cannot leave a note on your own recipe.'
REVIEW_SUBMIT_INVALID_FIELDS = 'Complete the note before sharing it.'
REVIEW_SUBMIT_SUCCESS = 'Thank you. Your note is now part of the page.'
REVIEW_SUBMIT_UPDATED = 'Your earlier note has been updated.'

REACTION_RATE_LIMIT = 'Too many reaction requests. Please give it a moment and try again.'
REACTION_EMOJI_REQUIRED = 'Choose an emoji before responding.'
REACTION_EMOJI_UNSUPPORTED = 'That reaction is unavailable right now.'
REACTION_REMOVED = 'Your reaction has been removed.'
REACTION_UPDATED = 'Your reaction has been updated.'
REACTION_ADDED = 'Your reaction has been added.'

RECIPE_UNAVAILABLE = 'This recipe is unavailable right now.'
RECIPE_PERMISSION_UPDATE = "You do not have permission to change this recipe's visibility."
RECIPE_INVALID_STATUS = 'That status is unavailable for this recipe.'
RECIPE_PERMISSION_DELETE = 'You do not have permission to remove this recipe.'

RECIPE_CREATE_RATE_LIMIT = 'Too many recipe publish attempts. Please give it a moment and try again.'
RECIPE_CREATE_STEPS_REQUIRED = 'Add at least one step so another cook can follow along.'
RECIPE_CREATE_INGREDIENTS_REQUIRED = 'Add at least one ingredient so another cook can cook from it.'
RECIPE_CREATE_DUPLICATE_IN_PROGRESS = 'Your previous publish is still being processed. Please give it a moment.'
RECIPE_CREATE_DUPLICATE_REDIRECT = 'This recipe was already published. We reopened the existing page.'
RECIPE_CREATE_DRAFT_READY = 'Your AI draft is ready to refine in Recipe Studio.'
RECIPE_CREATE_SUCCESS = 'Your recipe has been published.'

REPORT_SUBMIT_SUCCESS = 'Thank you for reporting. Our stewards will review this shortly.'
REPORT_ALREADY_OPEN = 'You already reported this content and it is still under review.'
REPORT_SUBMIT_INVALID = 'Choose a valid report reason before submitting.'
REPORT_SUBMIT_RATE_LIMIT = 'Too many report submissions. Please give it a moment and try again.'
REPORT_QUEUE_PERMISSION = 'You do not have permission to review reports.'
REPORT_RESOLVE_RATE_LIMIT = 'Too many report decisions. Please give it a moment and try again.'
REPORT_RESOLVE_INVALID = 'Choose a valid moderation action before submitting.'
REPORT_ALREADY_REVIEWED = 'This report was already processed.'
REPORT_SELF_REPORT_NOT_ALLOWED = 'You cannot report your own content.'
REPORT_STATUS_RESOLVED = 'The report has been marked as resolved.'
REPORT_STATUS_DISMISSED = 'The report has been dismissed.'

REVIEW_PERMISSION_DELETE = 'You do not have permission to remove this note.'
REVIEW_REMOVED = 'The note has been removed and its pending reports are resolved.'
REVIEW_ALREADY_REMOVED = 'That note is already removed.'
REVIEW_DELETE_REPORT_RESOLUTION_NOTE = 'Resolved automatically: a steward removed the reported note.'


def recipe_status_already_message(status_display: str) -> str:
    """Build info message when target recipe status is unchanged."""
    return f'This recipe is already marked as {status_display}.'


def recipe_status_updated_message(status_display: str) -> str:
    """Build success message after recipe status update."""
    return f'This recipe is now marked as {status_display}.'


def recipe_removed_message(recipe_title: str) -> str:
    """Build success message after recipe deletion."""
    return f'This recipe has been removed: {recipe_title}.'
