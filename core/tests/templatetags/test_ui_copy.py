"""Tests for shared UI copy rendering helpers."""

from django.template import Context, Template
from django.test import SimpleTestCase

from core.templatetags.ui_copy import ui_label_filter, ui_title_filter


class UICopyTemplateTagTests(SimpleTestCase):
    """UI copy helpers should keep label casing readable and predictable."""

    def test_filter_renders_sentence_case_labels(self):
        cases = {
            'start a recipe draft': 'Start a recipe draft',
            'Save to recipe box': 'Save to recipe box',
            'watch on Bilibili': 'Watch on Bilibili',
            'ai-assisted drafts': 'AI-assisted drafts',
            'AI recipe studio': 'AI recipe studio',
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(ui_label_filter(source), expected)

    def test_filter_handles_none(self):
        self.assertEqual(ui_label_filter(None), '')

    def test_tag_accepts_literal_strings(self):
        rendered = Template("{% load ui_copy %}{% ui_label 'see what is rising' %}").render(Context())
        self.assertEqual(rendered, 'See what is rising')

    def test_title_filter_uses_title_case_rules(self):
        self.assertEqual(ui_title_filter('what strong drafts do'), 'What Strong Drafts Do')

    def test_title_filter_preserves_small_words_and_acronyms(self):
        self.assertEqual(ui_title_filter('best inputs start here for ai drafts'), 'Best Inputs Start Here for AI Drafts')

    def test_title_tag_accepts_literal_strings(self):
        rendered = Template("{% load ui_copy %}{% ui_title 'save to recipe box' %}").render(Context())
        self.assertEqual(rendered, 'Save to Recipe Box')
