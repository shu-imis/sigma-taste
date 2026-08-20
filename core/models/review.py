"""Review and reaction domain models."""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Review(models.Model):
    """User review content and score for a recipe."""

    recipe = models.ForeignKey('core.Recipe', on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='reviews')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    content = models.TextField(blank=True)
    is_anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['recipe', 'user'], name='unique_recipe_user_review'),
        ]
        indexes = [
            models.Index(fields=['created_at'], name='review_created_idx'),
            models.Index(fields=['recipe', 'created_at'], name='review_recipe_created_idx'),
        ]


class Reaction(models.Model):
    """Emoji reaction to a review."""

    EMOJI_CHOICES = (
        ('👍', 'Thumbs Up'),
        ('😋', 'Tasty'),
        ('🤔', 'Thoughtful'),
    )

    review = models.ForeignKey('core.Review', on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reactions')
    emoji = models.CharField(max_length=10, choices=EMOJI_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['review', 'user'], name='unique_review_user'),
        ]
