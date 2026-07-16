"""Smoke tests for baseline project integrity."""

import re

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse


class DatabaseConfigurationTests(SimpleTestCase):
    """SQLite should wait on locks instead of failing fast under concurrent writes."""

    def test_sqlite_default_connection_sets_lock_timeout(self):
        self.assertEqual(settings.DATABASES['default']['OPTIONS']['timeout'], 20)


class RequestTracingTests(TestCase):
    """Middleware should stamp tracing and security headers."""

    def test_response_includes_request_id_header(self):
        response = self.client.get(reverse('web-home'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('X-Request-ID', response.headers)
        self.assertTrue(response.headers['X-Request-ID'])

    def test_safe_client_request_id_is_reflected(self):
        response = self.client.get(reverse('web-home'), HTTP_X_REQUEST_ID='client-req-42')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['X-Request-ID'], 'client-req-42')

    def test_unsafe_client_request_id_is_replaced_with_generated_id(self):
        response = self.client.get(reverse('web-home'), HTTP_X_REQUEST_ID='bad\r\ninjected: yes')
        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.headers['X-Request-ID'], r'^[0-9a-f]{32}$')

    def test_overlong_client_request_id_is_replaced_with_generated_id(self):
        response = self.client.get(reverse('web-home'), HTTP_X_REQUEST_ID='a' * 65)
        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.headers['X-Request-ID'], r'^[0-9a-f]{32}$')

    def test_response_includes_security_headers(self):
        response = self.client.get(reverse('web-home'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('Content-Security-Policy', response.headers)
        self.assertIn('Permissions-Policy', response.headers)
        self.assertNotIn("'unsafe-inline'", response.headers['Content-Security-Policy'])
        self.assertIn("object-src 'none'", response.headers['Content-Security-Policy'])

    def test_response_uses_nonce_backed_critical_paint_style(self):
        response = self.client.get(reverse('web-home'))
        self.assertEqual(response.status_code, 200)

        match = re.search(r'<style nonce="([^"]+)">', response.content.decode('utf-8'))
        self.assertIsNotNone(match)

        nonce = match.group(1)
        self.assertIn(f"'nonce-{nonce}'", response.headers['Content-Security-Policy'])
