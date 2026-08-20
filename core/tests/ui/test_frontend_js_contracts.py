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
        self.assertIn("event.key !== 'Escape'", content)
        self.assertIn("event.target.closest('.nav-shell')", content)
        self.assertIn("setMenuState(false, { focusToggle: true })", content)

    def test_form_progress_updates_accessibility_state(self):
        content = self._read_script('form_progress.js')
        self.assertIn("form.setAttribute('aria-busy', 'true')", content)
        self.assertIn("progress.setAttribute('aria-hidden', 'false')", content)
        self.assertIn("progressBar.setAttribute('aria-valuetext'", content)
        self.assertIn("titleNode.textContent = text.title", content)
