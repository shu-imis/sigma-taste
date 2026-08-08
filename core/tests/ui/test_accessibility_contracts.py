"""Accessibility contracts: ARIA id pairing, landmarks, naming, contrast tokens, CJK lang annotations, and optional labels."""

import re

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.models import Reaction, Review
from core.tests.utils import find_core_dir, make_recipe, make_user

DESCRIBEDBY_RE = re.compile(r'aria-describedby="([^"]+)"')
ID_RE = re.compile(r'\bid="([^"]+)"')

_STYLES_DIR = find_core_dir() / 'static' / 'core' / 'css'
_INVALID_RECIPE_CREATE_PAYLOAD = {
    'title': '',
    'cuisine': '',
    'cooking_time': 1,
    'difficulty': 'easy',
    'steps_text': '',
    'ingredients_text': '',
}


def dangling_aria_describedby(html: str) -> list[str]:
    """Return aria-describedby idrefs that have no matching element id."""
    referenced = set()
    for match in DESCRIBEDBY_RE.finditer(html):
        referenced.update(match.group(1).split())
    defined = set(ID_RE.findall(html))
    return sorted(referenced - defined)


class AriaDescribedbyPairingTests(TestCase):
    """Every aria-describedby idref Django renders must resolve to a real element."""

    @classmethod
    def setUpTestData(cls):
        cls.author = make_user(
            username='a11y-author',
            email='a11y-author@example.com',
            first_name='A11y',
            last_name='Author',
        )
        cls.viewer = make_user(
            username='a11y-viewer',
            email='a11y-viewer@example.com',
            first_name='A11y',
            last_name='Viewer',
        )
        cls.recipe = make_recipe(author=cls.author, title='Pairing fixture')

    def assert_no_dangling(self, response):
        html = response.content.decode('utf-8')
        self.assertEqual(dangling_aria_describedby(html), [])

    def test_public_pages_pair_every_aria_describedby_reference(self):
        for route_name in ('web-home', 'web-login', 'web-register', 'web-boards'):
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assert_no_dangling(response)
        response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))
        self.assertEqual(response.status_code, 200)
        self.assert_no_dangling(response)

    def test_authenticated_form_pages_pair_every_aria_describedby_reference(self):
        self.client.force_login(self.author)
        for route_name in ('web-recipe-create', 'web-ai-generate', 'web-profile'):
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assert_no_dangling(response)
        # The report form refuses self-reports, so open it as another member.
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('web-report-recipe', args=[self.recipe.id]))
        self.assertEqual(response.status_code, 200)
        self.assert_no_dangling(response)

    def test_error_states_pair_every_aria_describedby_reference(self):
        register_response = self.client.post(
            reverse('web-register'),
            {
                'username': 'new-member',
                'email': 'new-member@example.com',
                'first_name': 'New',
                'last_name': 'Member',
                'password1': 'short',
                'password2': 'mismatch',
            },
        )
        self.assertEqual(register_response.status_code, 200)
        self.assert_no_dangling(register_response)

        login_response = self.client.post(reverse('web-login'), {'username': '', 'password': ''})
        self.assertEqual(login_response.status_code, 200)
        self.assert_no_dangling(login_response)

        self.client.force_login(self.author)
        create_response = self.client.post(
            reverse('web-recipe-create'),
            _INVALID_RECIPE_CREATE_PAYLOAD,
        )
        self.assertEqual(create_response.status_code, 200)
        self.assert_no_dangling(create_response)

    def test_register_page_shows_password_rules_only_after_failed_submit(self):
        response = self.client.get(reverse('web-register'))
        self.assertEqual(response.status_code, 200)
        # Untouched form stays quiet: no preemptive hints under any field.
        self.assertNotContains(response, 'at least 8 characters')
        self.assertNotContains(response, '_helptext')

        response = self.client.post(
            reverse('web-register'),
            {
                'username': 'short-pass-member',
                'email': 'short-pass-member@example.com',
                'first_name': 'Short',
                'last_name': 'Pass',
                'password1': 'short',
                'password2': 'short',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'at least 8 characters')

    def test_register_page_avoids_autofocus(self):
        response = self.client.get(reverse('web-register'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'autofocus')

    def test_create_page_renders_help_text_with_paired_ids(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse('web-recipe-create'))
        self.assertEqual(response.status_code, 200)
        for field_name in ('steps_text', 'ingredients_text', 'tutorial_video_url'):
            with self.subTest(field=field_name):
                self.assertContains(response, f'aria-describedby="id_{field_name}_helptext"', html=False)
                self.assertContains(response, f'id="id_{field_name}_helptext"', html=False)

    def test_profile_page_renders_preference_help_text_with_paired_ids(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse('web-profile'))
        self.assertEqual(response.status_code, 200)
        for field_id in ('id_pref-allergies', 'id_pref-preferred_cuisines'):
            with self.subTest(field_id=field_id):
                self.assertContains(response, f'aria-describedby="{field_id}_helptext"', html=False)
                self.assertContains(response, f'id="{field_id}_helptext"', html=False)

    def test_field_error_items_carry_the_referenced_error_id(self):
        self.client.force_login(self.author)
        response = self.client.post(
            reverse('web-recipe-create'),
            _INVALID_RECIPE_CREATE_PAYLOAD,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_title_error"', html=False)
        self.assertContains(response, 'aria-describedby="id_title_error"', html=False)


class LandmarkAndNamingTests(TestCase):
    """Landmark elements and accessible names stay stable."""

    @classmethod
    def setUpTestData(cls):
        cls.author = make_user(
            username='landmark-author',
            email='landmark-author@example.com',
            first_name='Landmark',
            last_name='Author',
        )
        cls.recipe = make_recipe(author=cls.author, title='Landmark fixture')

    def test_search_forms_expose_search_landmark(self):
        for route_name in ('web-home', 'web-boards'):
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'role="search"')

    def test_page_footer_uses_footer_landmark_element(self):
        response = self.client.get(reverse('web-home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<footer class="footer">', html=False)

    def test_report_dialog_names_itself_from_its_heading(self):
        viewer = make_user(
            username='dialog-viewer',
            email='dialog-viewer@example.com',
            first_name='Dialog',
            last_name='Viewer',
        )
        self.client.force_login(viewer)
        response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            '<dialog class="report-dialog" data-report-dialog aria-labelledby="report-dialog-title">',
            html=False,
        )
        self.assertContains(response, 'id="report-dialog-title" data-report-dialog-title', html=False)

    def test_reaction_buttons_expose_pressed_state(self):
        reviewer = make_user(
            username='reaction-reviewer',
            email='reaction-reviewer@example.com',
            first_name='Reaction',
            last_name='Reviewer',
        )
        viewer = make_user(
            username='reaction-viewer',
            email='reaction-viewer@example.com',
            first_name='Reaction',
            last_name='Viewer',
        )
        review = Review.objects.create(recipe=self.recipe, user=reviewer, rating=5, content='Great weeknight dinner.')
        self.client.force_login(viewer)

        response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-pressed="false"', count=2)
        self.assertNotContains(response, 'aria-pressed="true"')

        Reaction.objects.create(review=review, user=viewer, emoji='👍')
        response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-pressed="true"', count=1)
        self.assertContains(response, 'aria-pressed="false"', count=1)


class CjkContentLangTests(TestCase):
    """CJK user content gets a lang annotation; English content stays bare."""

    @classmethod
    def setUpTestData(cls):
        cls.author = make_user(
            username='lang-author',
            email='lang-author@example.com',
            first_name='Lang',
            last_name='Author',
        )

    def test_cjk_recipe_title_and_description_carry_lang(self):
        recipe = make_recipe(author=self.author, title='番茄炒蛋', description='家常快手菜，酸甜开胃。')

        home_response = self.client.get(reverse('web-home'))
        self.assertEqual(home_response.status_code, 200)
        detail_url = reverse('web-recipe-detail', args=[recipe.id])
        self.assertContains(
            home_response,
            f'class="card-community-title-link" href="{detail_url}" lang="zh-Hans"',
            html=False,
        )
        self.assertContains(home_response, 'card-community-copy" lang="zh-Hans"', html=False)

        detail_response = self.client.get(detail_url)
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, '<h1 lang="zh-Hans">番茄炒蛋</h1>', html=False)
        self.assertContains(detail_response, '<p lang="zh-Hans">家常快手菜，酸甜开胃。</p>', html=False)

    def test_cjk_review_content_carries_lang(self):
        recipe = make_recipe(author=self.author, title='Lang review fixture')
        reviewer = make_user(
            username='lang-reviewer',
            email='lang-reviewer@example.com',
            first_name='Lang',
            last_name='Reviewer',
        )
        Review.objects.create(recipe=recipe, user=reviewer, rating=4, content='外脆里嫩，火候刚好。')
        response = self.client.get(reverse('web-recipe-detail', args=[recipe.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<p class="review-content" lang="zh-Hans">外脆里嫩，火候刚好。</p>', html=False)

    def test_english_content_has_no_lang_override(self):
        recipe = make_recipe(author=self.author, title='Plain fixture', description='A simple pan dinner.')
        reviewer = make_user(
            username='plain-reviewer',
            email='plain-reviewer@example.com',
            first_name='Plain',
            last_name='Reviewer',
        )
        Review.objects.create(recipe=recipe, user=reviewer, rating=4, content='Solid weeknight dinner.')
        response = self.client.get(reverse('web-recipe-detail', args=[recipe.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<p class="review-content">Solid weeknight dinner.</p>', html=False)
        self.assertNotContains(response, 'lang="zh-Hans"')


class OptionalLabelConventionTests(TestCase):
    """Optional fields render the shared ' (optional)' label suffix everywhere."""

    @classmethod
    def setUpTestData(cls):
        cls.author = make_user(
            username='label-author',
            email='label-author@example.com',
            first_name='Label',
            last_name='Author',
        )
        cls.recipe = make_recipe(author=cls.author, title='Label fixture')

    def test_create_form_optional_labels(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse('web-recipe-create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<label for="id_description">Description (Optional)</label>', html=False)
        self.assertContains(response, '<label for="id_flavor">Flavor (Optional)</label>', html=False)
        self.assertContains(response, '<label for="id_tutorial_video_url">Tutorial Video Link (Optional)</label>', html=False)

    def test_report_form_optional_labels(self):
        reporter = make_user(
            username='label-reporter',
            email='label-reporter@example.com',
            first_name='Label',
            last_name='Reporter',
        )
        self.client.force_login(reporter)
        response = self.client.get(reverse('web-report-recipe', args=[self.recipe.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<label for="report-page-details">Report Details (Optional)</label>', html=False)


def _srgb_channel(value: float) -> float:
    value = value / 255
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def _luminance(rgb: tuple[float, float, float]) -> float:
    r, g, b = (_srgb_channel(part) for part in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(fg: tuple[float, float, float], bg: tuple[float, float, float]) -> float:
    lighter, darker = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def _parse_color(value: str, over: tuple[float, float, float]) -> tuple[float, float, float]:
    """Resolve a hex or rgba() token value to an opaque rgb triple."""
    value = value.strip()
    if value.startswith('#'):
        hex_digits = value[1:]
        if len(hex_digits) == 3:
            hex_digits = ''.join(char * 2 for char in hex_digits)
        return tuple(int(hex_digits[index:index + 2], 16) for index in (0, 2, 4))
    match = re.fullmatch(r'rgba?\(\s*(\d+),\s*(\d+),\s*(\d+)(?:,\s*([0-9.]+))?\s*\)', value)
    if not match:
        raise ValueError(f'Unsupported color token: {value}')
    red, green, blue = (int(match.group(index)) for index in (1, 2, 3))
    alpha = float(match.group(4)) if match.group(4) is not None else 1.0
    return tuple(round(alpha * channel + (1 - alpha) * over[index]) for index, channel in enumerate((red, green, blue)))


class ContrastTokenTests(SimpleTestCase):
    """Lock the WCAG contrast ratios the audit fixed into the design tokens."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tokens = (_STYLES_DIR / 'tokens.css').read_text(encoding='utf-8')

    def _token_rgb(self, name: str, *, over: tuple[float, float, float]) -> tuple[float, float, float]:
        match = re.search(rf'{re.escape(name)}\s*:\s*([^;]+);', self._tokens)
        self.assertIsNotNone(match, f'{name} must stay defined in tokens.css')
        return _parse_color(match.group(1), over)

    def test_danger_token_meets_aa_against_inverse_button_text(self):
        danger = self._token_rgb('--danger', over=(255, 255, 255))
        ink_inverse = self._token_rgb('--ink-inverse', over=(255, 255, 255))
        self.assertGreaterEqual(_contrast_ratio(ink_inverse, danger), 4.5)

    def test_warn_token_meets_aa_against_surface(self):
        warn = self._token_rgb('--warn', over=(255, 255, 255))
        surface = self._token_rgb('--surface', over=(255, 255, 255))
        self.assertGreaterEqual(_contrast_ratio(warn, surface), 4.5)

    def test_placeholder_token_stays_readable_against_inputs(self):
        surface = self._token_rgb('--surface', over=(255, 255, 255))
        placeholder = self._token_rgb('--placeholder', over=surface)
        self.assertGreaterEqual(_contrast_ratio(placeholder, surface), 4.5)

    def test_input_focus_ring_uses_solid_two_px_ring(self):
        self.assertIn('--focus-shadow: 0 0 0 2px var(--focus-ring);', self._tokens)


class ContentLinkStyleTests(SimpleTestCase):
    """In-copy links must be identifiable without relying on color alone."""

    def test_content_links_keep_underline(self):
        content_css = (_STYLES_DIR / 'content.css').read_text(encoding='utf-8')
        self.assertRegex(
            content_css,
            re.compile(
                r'\.meta a,\s*\.card-body p a,\s*\.list-link-title\s*\{[^}]*text-decoration:\s*underline',
                re.DOTALL,
            ),
        )
