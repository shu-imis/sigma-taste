"""Tests for shared UI copy rendering helpers."""

from django.template import Context, Template
from django.test import SimpleTestCase

from core.templatetags.ui_copy import ui_label_filter, ui_title_filter


class UICopyTemplateTagTests(SimpleTestCase):
    """UI copy helpers should keep uppercase rendering predictable."""

    def test_filter_uppercases_system_copy(self):
        self.assertEqual(ui_label_filter('Start a recipe draft'), 'START A RECIPE DRAFT')

    def test_filter_handles_none(self):
        self.assertEqual(ui_label_filter(None), '')

    def test_tag_accepts_literal_strings(self):
        rendered = Template("{% load ui_copy %}{% ui_label 'See what is rising' %}").render(Context())
        self.assertEqual(rendered, 'SEE WHAT IS RISING')

    def test_tag_accepts_context_variables(self):
        rendered = Template("{% load ui_copy %}{% ui_label label %}").render(
            Context({'label': 'Shape my profile'})
        )
        self.assertEqual(rendered, 'SHAPE MY PROFILE')

    def test_title_filter_uses_title_case_rules(self):
        self.assertEqual(ui_title_filter('what strong drafts do'), 'What Strong Drafts Do')

    def test_title_filter_preserves_small_words_and_acronyms(self):
        self.assertEqual(ui_title_filter('best inputs start here for ai drafts'), 'Best Inputs Start Here for AI Drafts')

    def test_title_tag_accepts_literal_strings(self):
        rendered = Template("{% load ui_copy %}{% ui_title 'save to my recipe box' %}").render(Context())
        self.assertEqual(rendered, 'Save to My Recipe Box')
