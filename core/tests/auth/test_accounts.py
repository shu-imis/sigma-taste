"""Account and authentication tests."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import DatabaseError, IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from core.tests.utils import make_user


class RegistrationPageTests(TestCase):
    """Registration validation messages should use human-friendly labels."""

    def test_register_errors_show_human_labels(self):
        response = self.client.post(
            reverse('web-register'),
            {
                'username': 'new-user',
                'email': 'new-user@example.com',
                'first_name': 'New',
                'last_name': 'User',
                'password1': 'short',
                'password2': 'mismatch',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Confirm Password:')
        self.assertNotContains(response, 'password1:')
        self.assertNotContains(response, 'password2:')
        self.assertContains(response, 'class="form-error-list"')
        self.assertContains(response, 'data-feedback-kind="form-error"')
        self.assertContains(response, '<li>')

    def test_register_form_has_autocomplete_attributes(self):
        response = self.client.get(reverse('web-register'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'autocomplete="username"')
        self.assertContains(response, 'autocomplete="email"')
        self.assertContains(response, 'autocomplete="given-name"')
        self.assertContains(response, 'autocomplete="family-name"')
        self.assertContains(response, 'autocomplete="new-password"', count=2)


class RegisterRateLimitTests(TestCase):
    """Registration endpoint should enforce configured throttling."""

    def setUp(self):
        cache.clear()

    @override_settings(RATE_LIMITS={'register': {'limit': 1, 'window': 60}})
    def test_register_rate_limit_blocks_second_attempt(self):
        payload = {
            'username': 'new-user',
            'email': 'new-user@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'password1': 'short',
            'password2': 'mismatch',
        }
        first = self.client.post(reverse('web-register'), payload)
        second = self.client.post(reverse('web-register'), payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertContains(second, 'Too many account creation attempts.')


class RegisterConflictTests(TestCase):
    """A uniqueness race at save time should surface as a form error, not a 500."""

    def setUp(self):
        cache.clear()

    @patch('core.views.pages.auth.RegisterForm.save', side_effect=IntegrityError('duplicate key'))
    def test_register_integrity_error_becomes_form_error(self, _mock_save):
        response = self.client.post(
            reverse('web-register'),
            {
                'username': 'jane-doe',
                'email': 'jane.doe@example.com',
                'first_name': 'Jane',
                'last_name': 'Doe',
                'password1': 'correct-horse-battery-72',
                'password2': 'correct-horse-battery-72',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'An account with those details already exists. Try signing in instead.')
        self.assertContains(response, 'data-feedback-kind="form-error"')
        self.assertEqual(get_user_model().objects.count(), 0)


class ProfileSaveTransactionTests(TestCase):
    """Profile and preference saves should commit together or not at all."""

    def setUp(self):
        cache.clear()
        self.user = make_user(
            username='jane-doe',
            email='jane.doe@example.com',
            first_name='Jane',
            last_name='Doe',
        )
        self.client.force_login(self.user)

    def _profile_payload(self):
        return {
            'profile-first_name': 'Janet',
            'profile-last_name': 'Doe',
            'profile-bio': '',
            'pref-allergies': '',
            'pref-preferred_cuisines': '',
            'pref-health_goal': 'none',
        }

    @patch('core.views.pages.auth.PreferenceForm.save', side_effect=DatabaseError('preference save failed'))
    def test_profile_change_rolls_back_when_preference_save_fails(self, _mock_save):
        with self.assertRaises(DatabaseError):
            self.client.post(reverse('web-profile'), self._profile_payload())

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Jane')


class AccountCreationTests(TestCase):
    """Custom user manager should enforce required identity fields."""

    def setUp(self):
        self.user_model = get_user_model()

    def test_regular_user_requires_identity_fields(self):
        with self.assertRaises(ValueError):
            self.user_model.objects.create_user(username='missing-profile', password='pwd-12345')

    def test_create_superuser_builds_steward_account(self):
        user = self.user_model.objects.create_superuser(
            username='site-admin',
            email='site-admin@example.com',
            first_name='Site',
            last_name='Admin',
            password='pwd-12345',
        )
        self.assertEqual(user.role, self.user_model.ROLE_STEWARD)
        self.assertTrue(user.is_steward)


class LoginRateLimitTests(TestCase):
    """Sign-in endpoint should enforce configured throttling."""

    def setUp(self):
        cache.clear()

    def test_login_form_has_autocomplete_attributes(self):
        response = self.client.get(reverse('web-login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'autocomplete="username"')
        self.assertContains(response, 'autocomplete="current-password"')

    @override_settings(RATE_LIMITS={'login': {'limit': 1, 'window': 60}})
    def test_login_rate_limit_blocks_second_attempt(self):
        first = self.client.post(reverse('web-login'), {'username': 'missing', 'password': 'wrong'})
        second = self.client.post(reverse('web-login'), {'username': 'missing', 'password': 'wrong'})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertContains(second, 'Too many sign-in attempts.')
        self.assertContains(second, 'data-feedback-kind="flash"')

    @override_settings(RATE_LIMITS={'login': {'limit': 30, 'window': 60}, 'login_account': {'limit': 2, 'window': 300}})
    def test_login_rate_limit_also_applies_per_account_username(self):
        first = self.client.post(reverse('web-login'), {'username': 'Throttle-Target', 'password': 'wrong'})
        second = self.client.post(reverse('web-login'), {'username': 'throttle-target', 'password': 'wrong'})
        self.assertNotContains(first, 'Too many sign-in attempts.')
        self.assertNotContains(second, 'Too many sign-in attempts.')

        third = self.client.post(reverse('web-login'), {'username': 'THROTTLE-TARGET', 'password': 'wrong'})
        self.assertContains(third, 'Too many sign-in attempts.')

        other_account = self.client.post(reverse('web-login'), {'username': 'other-account', 'password': 'wrong'})
        self.assertNotContains(other_account, 'Too many sign-in attempts.')
        self.assertContains(other_account, "We couldn't sign you in with those details. Please try again.")

    @override_settings(RATE_LIMITS={'login': {'limit': 30, 'window': 60}, 'login_account': {'limit': 2, 'window': 300}})
    def test_login_account_rate_limit_is_scoped_per_ip(self):
        # Two failed attempts from one IP exhaust that IP's bucket for the account.
        self.client.post(reverse('web-login'), {'username': 'target-user', 'password': 'wrong'}, REMOTE_ADDR='203.0.113.10')
        self.client.post(reverse('web-login'), {'username': 'target-user', 'password': 'wrong'}, REMOTE_ADDR='203.0.113.10')
        blocked = self.client.post(reverse('web-login'), {'username': 'target-user', 'password': 'wrong'}, REMOTE_ADDR='203.0.113.10')
        self.assertContains(blocked, 'Too many sign-in attempts.')

        # The same account remains reachable from another network, so an attacker
        # cannot lock out the legitimate owner from afar.
        elsewhere = self.client.post(reverse('web-login'), {'username': 'target-user', 'password': 'wrong'}, REMOTE_ADDR='203.0.113.11')
        self.assertNotContains(elsewhere, 'Too many sign-in attempts.')
        self.assertContains(elsewhere, "We couldn't sign you in with those details. Please try again.")

    def test_invalid_login_uses_shared_form_error_block(self):
        response = self.client.post(reverse('web-login'), {'username': 'missing', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "We couldn't sign you in with those details. Please try again.")
        self.assertContains(response, 'data-feedback-kind="form-error"')


class LoginRedirectTests(TestCase):
    """Sign-in should preserve safe next redirect targets."""

    def setUp(self):
        self.user = make_user(
            username='redirect-user',
            email='redirect-user@example.com',
            first_name='Redirect',
            last_name='User',
        )

    def test_login_redirects_to_safe_next_url(self):
        response = self.client.post(
            reverse('web-login'),
            {
                'username': 'redirect-user',
                'password': 'pwd-12345',
                'next': reverse('web-recipe-create'),
            },
        )
        self.assertRedirects(response, reverse('web-recipe-create'), fetch_redirect_response=False)

    def test_login_ignores_external_next_url(self):
        response = self.client.post(
            reverse('web-login'),
            {
                'username': 'redirect-user',
                'password': 'pwd-12345',
                'next': 'https://example.com/evil',
            },
        )
        self.assertRedirects(response, reverse('web-home'), fetch_redirect_response=False)


class LogoutMethodTests(TestCase):
    """Sign-out endpoint should require POST and clear session auth state."""

    def setUp(self):
        self.user = make_user(
            username='logout-user',
            email='logout-user@example.com',
            first_name='Logout',
            last_name='User',
        )

    def test_logout_rejects_get(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('web-logout'))
        self.assertEqual(response.status_code, 405)

    def test_logout_via_post_clears_auth_session(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('web-logout'))
        self.assertRedirects(response, reverse('web-home'), fetch_redirect_response=False)
        follow_up = self.client.get(reverse('web-profile'))
        expected = f"{reverse('web-login')}?next={reverse('web-profile')}"
        self.assertRedirects(follow_up, expected, fetch_redirect_response=False)
