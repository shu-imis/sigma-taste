"""Shared helpers for the test suite."""

from pathlib import Path


def find_core_dir() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        has_models_module = (parent / 'models.py').exists() or (parent / 'models').is_dir()
        if parent.name == 'core' and has_models_module:
            return parent
    raise RuntimeError('Unable to locate core package root from test path.')
