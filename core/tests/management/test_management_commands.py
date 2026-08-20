"""Management command behavior tests."""

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError
from django.test import TestCase


class CreateStewardCommandTests(TestCase):
    """create_steward should support interactive and flag-based execution."""

    def setUp(self):
        self.user_model = get_user_model()

    @patch('core.management.commands.create_steward.getpass')
    @patch('core.management.commands.create_steward.input')
    def test_create_steward_interactively(self, mock_input, mock_getpass):
        mock_input.side_effect = [
            'steward-interactive',
            'steward-interactive@example.com',
            'Steward',
            'Interactive',
        ]
        mock_getpass.side_effect = ['StrongPwd-123', 'StrongPwd-123']
        out = StringIO()

        call_command('create_steward', stdout=out)

        user = self.user_model.objects.get(username='steward-interactive')
        self.assertEqual(user.email, 'steward-interactive@example.com')
        self.assertEqual(user.first_name, 'Steward')
        self.assertEqual(user.last_name, 'Interactive')
        self.assertEqual(user.role, self.user_model.ROLE_STEWARD)
        self.assertIn('steward.create ok', out.getvalue())

    def test_create_steward_no_input_requires_required_flags(self):
        with self.assertRaises(CommandError):
            call_command('create_steward', no_input=True)

    def test_create_steward_no_input_with_flags(self):
        call_command(
            'create_steward',
            username='steward-cli',
            email='steward-cli@example.com',
            first_name='Steward',
            last_name='Cli',
            password='StrongPwd-123',
            no_input=True,
        )

        user = self.user_model.objects.get(username='steward-cli')
        self.assertEqual(user.role, self.user_model.ROLE_STEWARD)

    def test_create_steward_rejects_email_that_normalizes_to_existing_user(self):
        self.user_model.objects.create_user(
            username='existing-member',
            email='steward-dupe@example.com',
            first_name='Existing',
            last_name='Member',
            password='pwd-12345',
        )

        with self.assertRaises(CommandError):
            call_command(
                'create_steward',
                username='steward-dupe',
                email='steward-dupe@EXAMPLE.COM',
                first_name='Steward',
                last_name='Dupe',
                password='StrongPwd-123',
                no_input=True,
            )

        self.assertFalse(self.user_model.objects.filter(username='steward-dupe').exists())

    def test_create_steward_integrity_conflict_raises_command_error(self):
        with patch.object(
            self.user_model.objects,
            'create_steward_user',
            side_effect=IntegrityError('duplicate key value violates unique constraint'),
        ):
            with self.assertRaises(CommandError) as caught:
                call_command(
                    'create_steward',
                    username='steward-race',
                    email='steward-race@example.com',
                    first_name='Steward',
                    last_name='Race',
                    password='StrongPwd-123',
                    no_input=True,
                )

        self.assertIn('already exists', str(caught.exception))
