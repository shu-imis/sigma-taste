"""WSGI entrypoint for Sigma Taste."""

import os

from django.core.wsgi import get_wsgi_application

from sigma_taste import settings as project_settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sigma_taste.settings')
project_settings.validate_runtime_settings()

application = get_wsgi_application()
