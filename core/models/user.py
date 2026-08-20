"""User and preference domain models."""

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Custom manager for application users with required identity fields."""

    REQUIRED_IDENTITY_FIELDS = ('email', 'first_name', 'last_name')

    @staticmethod
    def _clean_text(value):
        return value.strip() if isinstance(value, str) else value

    def _normalize_identity(self, username, email, extra_fields):
        clean_username = self._clean_text(username)
        normalized_email = self.normalize_email(email)
        first_name = self._clean_text(extra_fields.get('first_name', ''))
        last_name = self._clean_text(extra_fields.get('last_name', ''))
        bio = self._clean_text(extra_fields.get('bio', '')) or ''

        if not clean_username:
            raise ValueError('Username is required.')

        identity_values = {
            'email': normalized_email,
            'first_name': first_name,
            'last_name': last_name,
        }
        missing_fields = [field for field in self.REQUIRED_IDENTITY_FIELDS if not identity_values[field]]
        if missing_fields:
            missing_text = ', '.join(missing_fields)
            raise ValueError(f'Missing required profile fields: {missing_text}.')

        extra_fields['first_name'] = first_name
        extra_fields['last_name'] = last_name
        extra_fields['bio'] = bio
        return clean_username, normalized_email, extra_fields

    def create_user(self, username, email=None, password=None, **extra_fields):
        username, email, extra_fields = self._normalize_identity(username, email, extra_fields)
        if not password:
            raise ValueError('Password is required.')
        extra_fields.setdefault('role', self.model.ROLE_MEMBER)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_steward_user(self, username, email=None, password=None, **extra_fields):
        """Create a steward account with the same profile requirements as members."""
        extra_fields['role'] = self.model.ROLE_STEWARD
        return self.create_user(username=username, email=email, password=password, **extra_fields)

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        """Create a superuser account; superusers map to stewards in this project."""
        return self.create_steward_user(username=username, email=email, password=password, **extra_fields)


class User(AbstractBaseUser):
    """Application user model with human profile fields."""

    ROLE_MEMBER = 'member'
    ROLE_STEWARD = 'steward'
    ROLE_CHOICES = (
        (ROLE_MEMBER, 'Member'),
        (ROLE_STEWARD, 'Steward'),
    )

    CAPABILITY_VIEW_NON_PUBLIC_RECIPE = 'view_non_public_recipe'
    CAPABILITY_UPDATE_RECIPE_STATUS = 'update_recipe_status'
    CAPABILITY_DELETE_ANY_RECIPE = 'delete_any_recipe'
    ROLE_CAPABILITIES = {
        ROLE_MEMBER: (),
        ROLE_STEWARD: (
            CAPABILITY_VIEW_NON_PUBLIC_RECIPE,
            CAPABILITY_UPDATE_RECIPE_STATUS,
            CAPABILITY_DELETE_ANY_RECIPE,
        ),
    }

    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)
    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']
    USERNAME_FIELD = 'username'
    EMAIL_FIELD = 'email'

    bio = models.TextField(max_length=500, blank=True)
    objects = UserManager()

    def __str__(self):
        return self.username

    def get_full_name(self) -> str:
        full_name = f'{self.first_name} {self.last_name}'.strip()
        return full_name or self.username

    def get_short_name(self) -> str:
        return self.first_name or self.username

    @property
    def is_steward(self) -> bool:
        return self.role == self.ROLE_STEWARD

    def has_capability(self, capability: str) -> bool:
        return capability in self.ROLE_CAPABILITIES.get(self.role, ())


class UserPreference(models.Model):
    """Personal taste and health preference profile for each user."""

    HEALTH_GOAL_CHOICES = (
        ('none', 'No specific goal'),
        ('lose', 'Weight loss'),
        ('gain', 'Muscle gain'),
    )

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='preference')
    spicy = models.BooleanField(default=False)
    sweet = models.BooleanField(default=False)
    sour = models.BooleanField(default=False)
    allergies = models.TextField(blank=True, help_text='Comma-separated')
    preferred_cuisines = models.TextField(blank=True, help_text='Comma-separated')
    health_goal = models.CharField(max_length=20, choices=HEALTH_GOAL_CHOICES, default='none')

    def __str__(self):
        return f'{self.user.username} preference'
