"""Static contracts for frontend interaction scripts."""

from django.test import SimpleTestCase

from core.tests.utils import find_core_dir


class FrontendScriptContractsTests(SimpleTestCase):
    """Guard key JS interaction behaviors without browser-level tooling."""

    _CORE_DIR = find_core_dir()
    _STATIC_JS_DIR = _CORE_DIR / 'static' / 'core' / 'js'

    def _read_script(self, name: str) -> str:
        return (self._STATIC_JS_DIR / name).read_text(encoding='utf-8')

    def test_nav_shell_handles_escape_and_outside_click_close(self):
        content = self._read_script('nav_shell.js')
        self.assertIn("addEventListener('keydown'", content)
        self.assertIn("'Escape'", content)
        self.assertIn("addEventListener('click'", content)
        self.assertIn("closest('.nav-shell')", content)
        self.assertIn("setAttribute('aria-expanded'", content)
        self.assertIn('.focus()', content)

    def test_form_progress_updates_accessibility_state(self):
        content = self._read_script('form_progress.js')
        self.assertIn("form.setAttribute('aria-busy', 'true')", content)
        self.assertIn("form.removeAttribute('aria-busy')", content)
        self.assertIn("progress.setAttribute('aria-hidden', 'false')", content)
        self.assertIn("progress.setAttribute('aria-hidden', 'true')", content)
        self.assertIn("setAttribute('aria-valuetext'", content)
        self.assertIn('submitBtn.disabled = true', content)
        self.assertIn('submitBtn.disabled = false', content)
        self.assertIn('if (submitting)', content)

    def test_card_tag_overflow_makes_hidden_tag_text_keyboard_reachable(self):
        content = self._read_script('card_tag_overflow.js')
        self.assertIn("row.setAttribute('title', fullText)", content)
        self.assertIn("row.setAttribute('tabindex', '0')", content)
        self.assertIn("row.setAttribute('role', 'group')", content)
        self.assertIn("row.setAttribute('aria-label', fullText)", content)
        self.assertIn("row.removeAttribute('tabindex')", content)
        self.assertIn("row.removeAttribute('aria-label')", content)
