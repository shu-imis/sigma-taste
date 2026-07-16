"""Content report model for the community moderation workflow."""

from django.conf import settings
from django.db import models


class ContentReport(models.Model):
    """User-submitted report for recipe or review content."""

    TARGET_RECIPE = 'recipe'
    TARGET_REVIEW = 'review'
    TARGET_CHOICES = (
        (TARGET_RECIPE, 'Recipe'),
        (TARGET_REVIEW, 'Review'),
    )

    REASON_SPAM = 'spam'
    REASON_ABUSE = 'abuse'
    REASON_MISLEADING = 'misleading'
    REASON_COPYRIGHT = 'copyright'
    REASON_OTHER = 'other'
    REASON_CHOICES = (
        (REASON_SPAM, 'Spam or promotion'),
        (REASON_ABUSE, 'Abusive language'),
        (REASON_MISLEADING, 'Misleading or unsafe guidance'),
        (REASON_COPYRIGHT, 'Copyright concern'),
        (REASON_OTHER, 'Other'),
    )

    STATUS_PENDING = 'pending'
    STATUS_RESOLVED = 'resolved'
    STATUS_DISMISSED = 'dismissed'
    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_RESOLVED, 'Resolved'),
        (STATUS_DISMISSED, 'Dismissed'),
    )

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='content_reports',
    )
    target_type = models.CharField(max_length=20, choices=TARGET_CHOICES)
    target_id = models.PositiveIntegerField()
    reason = models.CharField(max_length=30, choices=REASON_CHOICES, default=REASON_OTHER)
    details = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='moderated_content_reports',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['reporter', 'target_type', 'target_id'],
                condition=models.Q(status='pending'),
                name='unique_pending_report_per_target',
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'created_at'], name='report_status_created_idx'),
            models.Index(fields=['target_type', 'target_id', 'status'], name='report_target_status_idx'),
            models.Index(fields=['reporter', 'status'], name='report_reporter_status_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.target_type}:{self.target_id} ({self.status})'
