"""Create a steward account from command line input."""

from getpass import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError


class Command(BaseCommand):
    """Create one steward account with steward capabilities."""

    help = 'Provision a steward account using the standard profile schema.'

    def add_arguments(self, parser):
        parser.add_argument('--username', help='Unique username.')
        parser.add_argument('--email', help='Unique email address.')
        parser.add_argument('--first-name', help='First name.')
        parser.add_argument('--last-name', help='Last name.')
        parser.add_argument('--password', help='Login password.')
        parser.add_argument('--bio', default='', help='Optional profile bio text.')
        parser.add_argument(
            '--no-input',
            action='store_true',
            help='Disable interactive prompts and require all required flags.',
        )

    def handle(self, *args, **options):
        user_model = get_user_model()
        non_interactive = bool(options.get('no_input'))

        username = self._collect_unique_identity_field(
            user_model=user_model,
            field_name='username',
            prompt='steward.username',
            option_name='username',
            raw_value=options.get('username'),
            non_interactive=non_interactive,
        )
        email = self._collect_unique_identity_field(
            user_model=user_model,
            field_name='email',
            prompt='steward.email',
            option_name='email',
            raw_value=options.get('email'),
            non_interactive=non_interactive,
            normalize=user_model.objects.normalize_email,
        )
        first_name = self._collect_required_text(
            raw_value=options.get('first_name'),
            prompt='steward.first_name',
            option_name='first-name',
            non_interactive=non_interactive,
        )
        last_name = self._collect_required_text(
            raw_value=options.get('last_name'),
            prompt='steward.last_name',
            option_name='last-name',
            non_interactive=non_interactive,
        )
        password = self._collect_password(
            raw_value=options.get('password'),
            non_interactive=non_interactive,
        )
        bio = self._clean(options.get('bio')) or ''

        try:
            user = user_model.objects.create_steward_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password,
                bio=bio,
            )
        except IntegrityError as exc:
            raise CommandError(
                'steward.create failed: a user with this username or email already exists.'
            ) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f'steward.create ok username={user.username} email={user.email}'
            )
        )

    @staticmethod
    def _clean(value):
        return value.strip() if isinstance(value, str) else ''

    def _read_text(self, prompt):
        try:
            return input(prompt)
        except (EOFError, KeyboardInterrupt) as exc:
            raise CommandError('interactive input aborted.') from exc

    def _read_secret(self, prompt):
        try:
            return getpass(prompt)
        except (EOFError, KeyboardInterrupt) as exc:
            raise CommandError('interactive input aborted.') from exc

    def _collect_required_text(self, *, raw_value, prompt, option_name, non_interactive):
        value = self._clean(raw_value)
        if value:
            return value
        if non_interactive:
            raise CommandError(f'--{option_name} is required when using --no-input.')

        while True:
            value = self._clean(self._read_text(f'{prompt}> '))
            if value:
                return value
            self.stderr.write(self.style.WARNING(f'{prompt} required'))

    def _collect_unique_identity_field(
        self,
        *,
        user_model,
        field_name,
        prompt,
        option_name,
        raw_value,
        non_interactive,
        normalize=None,
    ):
        candidate = raw_value
        while True:
            value = self._collect_required_text(
                raw_value=candidate,
                prompt=prompt,
                option_name=option_name,
                non_interactive=non_interactive,
            )
            if normalize is not None:
                value = normalize(value)
            if not user_model.objects.filter(**{field_name: value}).exists():
                return value

            if non_interactive or self._clean(candidate):
                raise CommandError(f'{prompt} already exists: {value}')

            self.stderr.write(self.style.WARNING(f'{prompt} already exists: {value}'))
            candidate = None

    def _collect_password(self, *, raw_value, non_interactive):
        raw_password = raw_value if isinstance(raw_value, str) else ''
        if raw_password:
            self._validate_password(raw_password)
            return raw_password

        if non_interactive:
            raise CommandError('--password is required when using --no-input.')

        while True:
            password = self._read_secret('steward.password> ')
            confirm = self._read_secret('steward.password.confirm> ')
            if not password:
                self.stderr.write(self.style.WARNING('steward.password required'))
                continue
            if password != confirm:
                self.stderr.write(self.style.WARNING('steward.password confirmation mismatch'))
                continue
            try:
                self._validate_password(password)
            except CommandError as exc:
                self.stderr.write(self.style.WARNING(str(exc)))
                continue
            return password

    def _validate_password(self, password):
        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages)) from exc
