"""Guardrails that keep styling primitives centralized in design tokens."""

import re

from django.test import SimpleTestCase

from core.tests.utils import find_core_dir


class StyleTokenGuardTests(SimpleTestCase):
    """Prevent silent drift from token-driven styling."""

    _CORE_DIR = find_core_dir()
    _STYLES_DIR = _CORE_DIR / 'static' / 'core' / 'css'

    ENTRYPOINT = _CORE_DIR.parent / 'templates' / 'core' / 'base.html'
    GUARDED_FILES = (
        _STYLES_DIR / 'layout.css',
        _STYLES_DIR / 'controls.css',
        _STYLES_DIR / 'hero.css',
        _STYLES_DIR / 'forms.css',
        _STYLES_DIR / 'cards.css',
        _STYLES_DIR / 'surfaces.css',
        _STYLES_DIR / 'recipe.css',
        _STYLES_DIR / 'content.css',
        _STYLES_DIR / 'utilities.css',
        _STYLES_DIR / 'responsive.css',
    )
    COLOR_LITERAL_PATTERN = re.compile(r'#[0-9a-fA-F]{3,8}\b|rgba?\(')

    def test_stylesheet_link_order_keeps_tokens_first(self):
        content = self.ENTRYPOINT.read_text(encoding='utf-8')
        links = re.findall(r'<link rel="stylesheet" href="\{% static \'core/css/([^\']+)\' %\}">', content)
        self.assertEqual(
            links,
            [
                'tokens.css',
                'layout.css',
                'controls.css',
                'hero.css',
                'forms.css',
                'cards.css',
                'surfaces.css',
                'recipe.css',
                'content.css',
                'responsive.css',
                'utilities.css',
            ],
        )

    def test_raw_color_literals_stay_in_tokens_only(self):
        violations = []
        for css_file in self.GUARDED_FILES:
            for line_number, line in enumerate(css_file.read_text(encoding='utf-8').splitlines(), start=1):
                for match in self.COLOR_LITERAL_PATTERN.finditer(line):
                    violations.append(f'{css_file.name}:{line_number} -> {match.group(0)}')

        self.assertFalse(
            violations,
            'Move raw color literals into tokens.css and reference them with CSS variables:\n'
            + '\n'.join(violations),
        )

    def test_home_community_cards_use_column_masonry_layout(self):
        surfaces_css = (self._STYLES_DIR / 'surfaces.css').read_text(encoding='utf-8')
        responsive_css = (self._STYLES_DIR / 'responsive.css').read_text(encoding='utf-8')
        self.assertRegex(
            surfaces_css,
            re.compile(r'\.home-main\s+\.cards\.cards-community\s*\{[^}]*column-count\s*:\s*2', re.S),
        )
        self.assertRegex(
            surfaces_css,
            re.compile(r'\.home-main\s+\.cards\.cards-community\s*>\s*\.card[^}]*break-inside\s*:\s*avoid', re.S),
        )
        self.assertRegex(
            responsive_css,
            re.compile(r'\.home-main\s+\.cards\.cards-community\s*\{[^}]*column-count\s*:\s*1', re.S),
        )

    def test_base_critical_css_color_literals_match_token_values(self):
        base_content = self.ENTRYPOINT.read_text(encoding='utf-8')
        style_match = re.search(r'<style\b[^>]*>(?P<css>.*?)</style>', base_content, re.S)
        self.assertIsNotNone(style_match, 'base.html should keep its inline critical-CSS block.')
        critical_css = style_match.group('css')

        tokens_css = (self._STYLES_DIR / 'tokens.css').read_text(encoding='utf-8')
        for token_name in ('--bg', '--bg-elevated', '--ink'):
            with self.subTest(token=token_name):
                token_match = re.search(
                    rf'{re.escape(token_name)}\s*:\s*(#[0-9a-fA-F]{{3,8}})\s*;',
                    tokens_css,
                )
                self.assertIsNotNone(token_match)
                self.assertIn(
                    token_match.group(1),
                    critical_css,
                    f'Critical CSS in base.html must mirror {token_name} from tokens.css.',
                )
