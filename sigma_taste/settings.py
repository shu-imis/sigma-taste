"""Project settings for Sigma Taste."""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.getenv('DEBUG', '1') == '1'
IS_TEST = 'test' in sys.argv
DEFAULT_DEV_SECRET_KEY = 'sigma-taste-dev-only-change-me-1d7f3a9c6b4e2f8a4c2d9e7f1a3b5c'
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', DEFAULT_DEV_SECRET_KEY)

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
    if host.strip()
]


def _is_weak_secret_key(value: str) -> bool:
    """Mirror Django deploy checks so weak production keys fail fast."""
    secret = str(value or '').strip()
    return len(secret) < 50 or len(set(secret)) < 5 or secret.startswith('django-insecure-')


def validate_runtime_settings() -> None:
    """Fail fast for unsafe production runtime configuration."""
    if not DEBUG and SECRET_KEY == DEFAULT_DEV_SECRET_KEY:
        raise RuntimeError('DJANGO_SECRET_KEY must be set when DEBUG=0.')
    if not DEBUG and _is_weak_secret_key(SECRET_KEY):
        raise RuntimeError('DJANGO_SECRET_KEY is too weak for production. Use a long random secret (50+ chars).')
    cache_backend = str(CACHES.get('default', {}).get('BACKEND', '')).lower()
    if not DEBUG and 'redis' not in cache_backend:
        raise RuntimeError('Redis cache backend is required when DEBUG=0.')

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.SecurityHeadersMiddleware',
    'core.middleware.RequestTracingMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'sigma_taste.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]
WSGI_APPLICATION = 'sigma_taste.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    },
}

AUTH_USER_MODEL = 'core.User'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LOGIN_URL = 'web-login'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

CACHE_BACKEND = os.getenv('CACHE_BACKEND', 'django.core.cache.backends.locmem.LocMemCache')
CACHE_LOCATION = os.getenv('CACHE_LOCATION', 'sigma-taste-default-cache')
CACHES = {
    'default': {
        'BACKEND': CACHE_BACKEND,
        'LOCATION': CACHE_LOCATION,
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

_SECURE_DEFAULT = '0' if (DEBUG or IS_TEST) else '1'
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', _SECURE_DEFAULT) == '1'
SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', _SECURE_DEFAULT) == '1'
CSRF_COOKIE_SECURE = os.getenv('CSRF_COOKIE_SECURE', _SECURE_DEFAULT) == '1'
SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
CSRF_COOKIE_SAMESITE = os.getenv('CSRF_COOKIE_SAMESITE', 'Lax')
SECURE_CONTENT_TYPE_NOSNIFF = os.getenv('SECURE_CONTENT_TYPE_NOSNIFF', _SECURE_DEFAULT) == '1'
X_FRAME_OPTIONS = os.getenv('X_FRAME_OPTIONS', 'DENY')
SECURE_REFERRER_POLICY = os.getenv('SECURE_REFERRER_POLICY', 'strict-origin-when-cross-origin')
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '0' if (DEBUG or IS_TEST) else '31536000'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv('SECURE_HSTS_INCLUDE_SUBDOMAINS', _SECURE_DEFAULT) == '1'
SECURE_HSTS_PRELOAD = os.getenv('SECURE_HSTS_PRELOAD', _SECURE_DEFAULT) == '1'
CONTENT_SECURITY_POLICY = os.getenv(
    'CONTENT_SECURITY_POLICY',
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'",
)
PERMISSIONS_POLICY = os.getenv('PERMISSIONS_POLICY', 'geolocation=(), microphone=(), camera=()')
CROSS_ORIGIN_OPENER_POLICY = os.getenv('CROSS_ORIGIN_OPENER_POLICY', 'same-origin')
CROSS_ORIGIN_RESOURCE_POLICY = os.getenv('CROSS_ORIGIN_RESOURCE_POLICY', 'same-site')

OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_DEFAULT_MODEL = os.getenv('OLLAMA_DEFAULT_MODEL', '')
OLLAMA_MODEL_CANDIDATES = [item.strip() for item in os.getenv('OLLAMA_MODEL_CANDIDATES', '').split(',') if item.strip()]
OLLAMA_TIMEOUT = int(os.getenv('OLLAMA_TIMEOUT', '180'))
OLLAMA_MODEL_LIST_CACHE_TTL = int(os.getenv('OLLAMA_MODEL_LIST_CACHE_TTL', '30'))
OLLAMA_MODEL_LIST_NEGATIVE_CACHE_TTL = int(os.getenv('OLLAMA_MODEL_LIST_NEGATIVE_CACHE_TTL', '5'))
IDEMPOTENCY_AI_GENERATE_WINDOW_SECONDS = int(os.getenv('IDEMPOTENCY_AI_GENERATE_WINDOW_SECONDS', '45'))
IDEMPOTENCY_RECIPE_CREATE_WINDOW_SECONDS = int(os.getenv('IDEMPOTENCY_RECIPE_CREATE_WINDOW_SECONDS', '45'))

# Trust forwarded headers only when the immediate proxy is explicitly allowed.
TRUSTED_PROXY_IPS = [
    ip.strip()
    for ip in os.getenv('TRUSTED_PROXY_IPS', '').split(',')
    if ip.strip()
]

RATE_LIMITS = {
    'register': {
        'limit': int(os.getenv('RATE_LIMIT_REGISTER_LIMIT', '6')),
        'window': int(os.getenv('RATE_LIMIT_REGISTER_WINDOW', '60')),
    },
    'login': {
        'limit': int(os.getenv('RATE_LIMIT_LOGIN_LIMIT', '12')),
        'window': int(os.getenv('RATE_LIMIT_LOGIN_WINDOW', '60')),
    },
    'login_account': {
        'limit': int(os.getenv('RATE_LIMIT_LOGIN_ACCOUNT_LIMIT', '8')),
        'window': int(os.getenv('RATE_LIMIT_LOGIN_ACCOUNT_WINDOW', '300')),
    },
    'ai_generate': {
        'limit': int(os.getenv('RATE_LIMIT_AI_GENERATE_LIMIT', '8')),
        'window': int(os.getenv('RATE_LIMIT_AI_GENERATE_WINDOW', '60')),
    },
    'ai_publish': {
        'limit': int(os.getenv('RATE_LIMIT_AI_PUBLISH_LIMIT', '12')),
        'window': int(os.getenv('RATE_LIMIT_AI_PUBLISH_WINDOW', '60')),
    },
    'reaction': {
        'limit': int(os.getenv('RATE_LIMIT_REACTION_LIMIT', '30')),
        'window': int(os.getenv('RATE_LIMIT_REACTION_WINDOW', '60')),
    },
    'review_submit': {
        'limit': int(os.getenv('RATE_LIMIT_REVIEW_SUBMIT_LIMIT', '20')),
        'window': int(os.getenv('RATE_LIMIT_REVIEW_SUBMIT_WINDOW', '60')),
    },
    'recipe_create': {
        'limit': int(os.getenv('RATE_LIMIT_RECIPE_CREATE_LIMIT', '10')),
        'window': int(os.getenv('RATE_LIMIT_RECIPE_CREATE_WINDOW', '60')),
    },
}
