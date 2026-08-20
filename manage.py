#!/usr/bin/env python
"""Command-line entrypoint for Sigma Taste management tasks."""
import os
import sys


def main():
    """Execute Django management commands."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sigma_taste.settings')
    try:
        from django.core.management import execute_from_command_line

        from sigma_taste import settings as project_settings
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    project_settings.validate_runtime_settings()
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
