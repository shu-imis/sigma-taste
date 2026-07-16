"""Content report submission and steward review queue tests."""

from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import ContentReport, Reaction, Review
from core.tests.utils import make_recipe, make_user


class ContentReportWorkflowTests(TestCase):
    """Community reporting should support submission, de-dup, and steward resolution."""

    def setUp(self):
        self.author = make_user(
            username='report-author',
            email='report-author@example.com',
            first_name='Report',
            last_name='Author',
        )
        self.reporter = make_user(
            username='report-member',
            email='report-member@example.com',
            first_name='Report',
            last_name='Member',
        )
        self.steward = make_user(
            role='steward',
            username='report-steward',
            email='report-steward@example.com',
            first_name='Report',
            last_name='Steward',
        )
        self.recipe = make_recipe(
            title='Reportable Recipe',
            description='Recipe report fixture.',
            author=self.author,
        )
        self.review = Review.objects.create(
            recipe=self.recipe,
            user=self.author,
            rating=4,
            content='Review report fixture.',
            is_anonymous=False,
        )

    def test_member_can_submit_recipe_report(self):
        self.client.force_login(self.reporter)

        response = self.client.post(
            reverse('web-report-recipe', args=[self.recipe.id]),
            {'reason': ContentReport.REASON_SPAM, 'details': 'Promotional links everywhere.'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Thank you for reporting. Our stewards will review this shortly.')
        self.assertEqual(ContentReport.objects.count(), 1)
        report = ContentReport.objects.get()
        self.assertEqual(report.target_type, ContentReport.TARGET_RECIPE)
        self.assertEqual(report.target_id, self.recipe.id)
        self.assertEqual(report.reason, ContentReport.REASON_SPAM)

    def test_duplicate_pending_report_is_not_duplicated(self):
        self.client.force_login(self.reporter)
        url = reverse('web-report-recipe', args=[self.recipe.id])

        first = self.client.post(url, {'reason': ContentReport.REASON_OTHER})
        second = self.client.post(url, {'reason': ContentReport.REASON_OTHER}, follow=True)

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 200)
        self.assertContains(second, 'You already reported this content and it is still under review.')
        self.assertEqual(ContentReport.objects.count(), 1)

    @patch(
        'core.views.pages.recipe.reports.ContentReport.objects.create',
        side_effect=IntegrityError('unique_pending_report_per_target'),
    )
    def test_report_submit_integrity_error_race_shows_friendly_message(self, _mock_create):
        # Simulates losing the check-then-create race: the database constraint
        # fires even though the pending-report lookup found nothing.
        self.client.force_login(self.reporter)

        response = self.client.post(
            reverse('web-report-recipe', args=[self.recipe.id]),
            {'reason': ContentReport.REASON_SPAM},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'You already reported this content and it is still under review.')

    def test_report_requires_a_valid_reason(self):
        self.client.force_login(self.reporter)

        response = self.client.post(
            reverse('web-report-recipe', args=[self.recipe.id]),
            {'reason': 'not-a-reason'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose a valid report reason before submitting.')
        self.assertEqual(ContentReport.objects.count(), 0)

    def test_author_cannot_report_own_recipe(self):
        self.client.force_login(self.author)

        response = self.client.post(
            reverse('web-report-recipe', args=[self.recipe.id]),
            {'reason': ContentReport.REASON_SPAM},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'You cannot report your own content.')
        self.assertEqual(ContentReport.objects.count(), 0)

    def test_author_cannot_report_own_review(self):
        self.client.force_login(self.author)

        response = self.client.post(
            reverse('web-report-review', args=[self.review.id]),
            {'reason': ContentReport.REASON_ABUSE},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'You cannot report your own content.')
        self.assertEqual(ContentReport.objects.count(), 0)

    def test_member_can_report_review(self):
        self.client.force_login(self.reporter)

        response = self.client.post(
            reverse('web-report-review', args=[self.review.id]),
            {'reason': ContentReport.REASON_MISLEADING},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ContentReport.objects.filter(
                target_type=ContentReport.TARGET_REVIEW,
                target_id=self.review.id,
            ).exists()
        )

    def test_anonymous_report_redirects_to_login(self):
        response = self.client.post(reverse('web-report-recipe', args=[self.recipe.id]), {'reason': 'spam'})

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('web-login'), response.url)
        self.assertEqual(ContentReport.objects.count(), 0)

    def test_non_steward_cannot_access_report_queue(self):
        self.client.force_login(self.reporter)

        response = self.client.get(reverse('web-report-queue'))

        self.assertRedirects(response, reverse('web-home'), fetch_redirect_response=False)

    def test_non_steward_cannot_resolve_report(self):
        report = ContentReport.objects.create(
            reporter=self.reporter,
            target_type=ContentReport.TARGET_RECIPE,
            target_id=self.recipe.id,
            reason=ContentReport.REASON_OTHER,
        )
        self.client.force_login(self.reporter)

        response = self.client.post(
            reverse('web-report-resolve', args=[report.id]),
            {'action': ContentReport.STATUS_RESOLVED},
        )

        self.assertRedirects(response, reverse('web-home'), fetch_redirect_response=False)
        report.refresh_from_db()
        self.assertEqual(report.status, ContentReport.STATUS_PENDING)

    def test_steward_can_resolve_pending_report(self):
        report = ContentReport.objects.create(
            reporter=self.reporter,
            target_type=ContentReport.TARGET_RECIPE,
            target_id=self.recipe.id,
            reason=ContentReport.REASON_OTHER,
            details='Needs moderation review.',
        )
        self.client.force_login(self.steward)

        response = self.client.post(
            reverse('web-report-resolve', args=[report.id]),
            {'action': ContentReport.STATUS_RESOLVED, 'resolution_note': 'Handled.'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'The report has been marked as resolved.')
        report.refresh_from_db()
        self.assertEqual(report.status, ContentReport.STATUS_RESOLVED)
        self.assertEqual(report.reviewer_id, self.steward.id)

    def test_steward_cannot_resolve_report_twice(self):
        report = ContentReport.objects.create(
            reporter=self.reporter,
            target_type=ContentReport.TARGET_RECIPE,
            target_id=self.recipe.id,
            reason=ContentReport.REASON_OTHER,
            status=ContentReport.STATUS_DISMISSED,
        )
        self.client.force_login(self.steward)

        response = self.client.post(
            reverse('web-report-resolve', args=[report.id]),
            {'action': ContentReport.STATUS_RESOLVED},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This report was already processed.')
        report.refresh_from_db()
        self.assertEqual(report.status, ContentReport.STATUS_DISMISSED)

    @patch('core.views.pages.recipe.reports.get_object_or_404')
    def test_stale_pending_read_never_overwrites_a_concurrent_resolution(self, mock_get_object):
        report = ContentReport.objects.create(
            reporter=self.reporter,
            target_type=ContentReport.TARGET_RECIPE,
            target_id=self.recipe.id,
            reason=ContentReport.REASON_OTHER,
        )
        # The view reads the row while it is still pending...
        mock_get_object.return_value = ContentReport.objects.get(id=report.id)
        # ...but a concurrent steward resolves it before our decision lands.
        ContentReport.objects.filter(id=report.id).update(
            status=ContentReport.STATUS_RESOLVED,
            reviewer=self.steward,
            reviewed_at=timezone.now(),
            resolution_note='First decision stands.',
        )
        other_steward = make_user(
            role='steward',
            username='report-steward-two',
            email='report-steward-two@example.com',
            first_name='Second',
            last_name='Steward',
        )
        self.client.force_login(other_steward)

        response = self.client.post(
            reverse('web-report-resolve', args=[report.id]),
            {'action': ContentReport.STATUS_DISMISSED, 'resolution_note': 'Overwritten decision.'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This report was already processed.')
        report.refresh_from_db()
        self.assertEqual(report.status, ContentReport.STATUS_RESOLVED)
        self.assertEqual(report.reviewer_id, self.steward.id)
        self.assertEqual(report.resolution_note, 'First decision stands.')

    def test_steward_queue_lists_pending_reports(self):
        ContentReport.objects.create(
            reporter=self.reporter,
            target_type=ContentReport.TARGET_REVIEW,
            target_id=self.review.id,
            reason=ContentReport.REASON_ABUSE,
            details='Hostile language.',
        )
        self.client.force_login(self.steward)

        response = self.client.get(reverse('web-report-queue'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Review report fixture.')
        self.assertContains(response, reverse('web-recipe-detail', args=[self.recipe.id]))

    def test_detail_page_renders_report_actions_for_authenticated_members(self):
        self.client.force_login(self.reporter)

        response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('web-report-recipe', args=[self.recipe.id]))
        self.assertContains(response, reverse('web-report-review', args=[self.review.id]))

    def test_detail_page_offers_report_dialog_with_page_fallback(self):
        self.client.force_login(self.reporter)

        response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-report-dialog')
        self.assertContains(response, 'data-report-dialog-trigger')
        for reason_value, _reason_label in ContentReport.REASON_CHOICES:
            self.assertContains(response, f'value="{reason_value}"')

    def test_report_form_page_exposes_all_reason_choices(self):
        self.client.force_login(self.reporter)

        for url in (
            reverse('web-report-recipe', args=[self.recipe.id]),
            reverse('web-report-review', args=[self.review.id]),
        ):
            response = self.client.get(url)

            self.assertEqual(response.status_code, 200)
            for reason_value, _reason_label in ContentReport.REASON_CHOICES:
                self.assertContains(response, f'value="{reason_value}"')

    def test_detail_page_hides_report_form_from_recipe_author(self):
        self.client.force_login(self.author)

        response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse('web-report-recipe', args=[self.recipe.id]))

    def test_steward_sees_queue_link_with_pending_count_on_detail(self):
        ContentReport.objects.create(
            reporter=self.reporter,
            target_type=ContentReport.TARGET_RECIPE,
            target_id=self.recipe.id,
            reason=ContentReport.REASON_SPAM,
        )
        self.client.force_login(self.steward)

        response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('web-report-queue'))
        self.assertContains(response, 'Report queue (1)')

    def test_steward_profile_surfaces_review_queue_link(self):
        self.client.force_login(self.steward)

        response = self.client.get(reverse('web-profile'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('web-report-queue'))

    def test_queue_shows_missing_target_fallback(self):
        ContentReport.objects.create(
            reporter=self.reporter,
            target_type=ContentReport.TARGET_RECIPE,
            target_id=999999,
            reason=ContentReport.REASON_SPAM,
        )
        self.client.force_login(self.steward)

        response = self.client.get(reverse('web-report-queue'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Target content is no longer available.')

    def test_steward_resolve_rejects_invalid_action(self):
        report = ContentReport.objects.create(
            reporter=self.reporter,
            target_type=ContentReport.TARGET_RECIPE,
            target_id=self.recipe.id,
            reason=ContentReport.REASON_OTHER,
        )
        self.client.force_login(self.steward)

        response = self.client.post(
            reverse('web-report-resolve', args=[report.id]),
            {'action': 'not-an-action'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose a valid moderation action before submitting.')
        report.refresh_from_db()
        self.assertEqual(report.status, ContentReport.STATUS_PENDING)


class ReviewModerationDeleteTests(TestCase):
    """Stewards can remove reported notes straight from the moderation queue."""

    def setUp(self):
        self.author = make_user(
            username='note-host-author',
            email='note-host-author@example.com',
            first_name='Note',
            last_name='Host',
        )
        self.member = make_user(
            username='note-writer',
            email='note-writer@example.com',
            first_name='Note',
            last_name='Writer',
        )
        self.steward = make_user(
            role='steward',
            username='note-steward',
            email='note-steward@example.com',
            first_name='Note',
            last_name='Steward',
        )
        self.recipe = make_recipe(
            title='Note Host Recipe',
            description='Review moderation fixture.',
            author=self.author,
        )
        self.review = Review.objects.create(
            recipe=self.recipe,
            user=self.member,
            rating=2,
            content='Spammy note content.',
            is_anonymous=False,
        )
        self.report = ContentReport.objects.create(
            reporter=self.author,
            target_type=ContentReport.TARGET_REVIEW,
            target_id=self.review.id,
            reason=ContentReport.REASON_SPAM,
        )

    def test_steward_delete_removes_note_and_reactions_and_resolves_pending_reports(self):
        Reaction.objects.create(review=self.review, user=self.author, emoji='👍')
        self.client.force_login(self.steward)

        response = self.client.post(reverse('web-review-delete', args=[self.review.id]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'The note has been removed and its pending reports are resolved.')
        self.assertFalse(Review.objects.filter(id=self.review.id).exists())
        self.assertEqual(Reaction.objects.count(), 0)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ContentReport.STATUS_RESOLVED)
        self.assertEqual(self.report.reviewer_id, self.steward.id)
        self.assertEqual(self.report.resolution_note, 'Resolved automatically: a steward removed the reported note.')
        self.assertIsNotNone(self.report.reviewed_at)

        detail = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, 'Spammy note content.')

    def test_member_cannot_delete_review(self):
        self.client.force_login(self.member)

        response = self.client.post(reverse('web-review-delete', args=[self.review.id]))

        self.assertRedirects(response, reverse('web-home'), fetch_redirect_response=False)
        self.assertTrue(Review.objects.filter(id=self.review.id).exists())
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ContentReport.STATUS_PENDING)

    def test_anonymous_delete_redirects_to_login(self):
        response = self.client.post(reverse('web-review-delete', args=[self.review.id]))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('web-login'), response.url)
        self.assertTrue(Review.objects.filter(id=self.review.id).exists())

    def test_repeat_delete_is_handled_gracefully(self):
        self.client.force_login(self.steward)
        self.client.post(reverse('web-review-delete', args=[self.review.id]))
        self.assertFalse(Review.objects.filter(id=self.review.id).exists())

        response = self.client.post(reverse('web-review-delete', args=[self.review.id]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'That note is already removed.')

    def test_queue_offers_remove_action_for_pending_note_reports(self):
        self.client.force_login(self.steward)

        response = self.client.get(reverse('web-report-queue'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('web-review-delete', args=[self.review.id]))
        self.assertContains(response, 'data-confirm-submit')

    def test_queue_shows_no_remove_action_for_recipe_targets(self):
        self.report.delete()
        ContentReport.objects.create(
            reporter=self.member,
            target_type=ContentReport.TARGET_RECIPE,
            target_id=self.recipe.id,
            reason=ContentReport.REASON_SPAM,
        )
        self.client.force_login(self.steward)

        response = self.client.get(reverse('web-report-queue'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Remove note')
