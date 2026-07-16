"""ASGI entrypoint for Sigma Taste."""

import os

from django.core.asgi import get_asgi_application

from sigma_taste import settings as project_settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sigma_taste.settings')
project_settings.validate_runtime_settings()

application = get_asgi_application()
