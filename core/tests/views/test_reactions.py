"""Review reaction behavior tests."""

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Reaction, Recipe, Review
from core.tests.utils import make_recipe, make_user


class ReviewReactionTests(TestCase):
    """Behavior checks for per-review emoji reactions."""

    def setUp(self):
        self.author = make_user(
            username='reaction-author',
            email='reaction-author@example.com',
            first_name='Reaction',
            last_name='Author',
        )
        self.reactor_1 = make_user(
            username='reaction-user-1',
            email='reaction-user-1@example.com',
            first_name='Reaction',
            last_name='UserOne',
        )
        self.reactor_2 = make_user(
            username='reaction-user-2',
            email='reaction-user-2@example.com',
            first_name='Reaction',
            last_name='UserTwo',
        )
        self.recipe = make_recipe(
            title='Reaction Test Recipe',
            description='for reaction behavior checks.',
            author=self.author,
        )
        self.review = Review.objects.create(
            recipe=self.recipe,
            user=self.author,
            rating=5,
            content='Solid test review',
        )

    def _create_extra_user(self, suffix):
        return make_user(
            username=f'reaction-extra-{suffix}',
            email=f'reaction-extra-{suffix}@example.com',
            first_name='Reaction',
            last_name=f'Extra{suffix}',
        )

    def _react(self, user, emoji):
        self.client.force_login(user)
        return self.client.post(reverse('web-review-react', args=[self.review.id]), {'emoji': emoji})

    def test_reaction_toggles_off_when_clicking_same_emoji(self):
        self._react(self.reactor_1, '👍')
        self.assertEqual(Reaction.objects.filter(review=self.review, user=self.reactor_1).count(), 1)

        self._react(self.reactor_1, '👍')
        self.assertFalse(Reaction.objects.filter(review=self.review, user=self.reactor_1).exists())

    def test_reaction_replaces_previous_emoji_for_same_user(self):
        self._react(self.reactor_1, '👍')
        self._react(self.reactor_1, '👎')

        qs = Reaction.objects.filter(review=self.review, user=self.reactor_1)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().emoji, '👎')

    def test_invalid_emoji_is_rejected(self):
        self._react(self.reactor_1, '🔥')
        self.assertFalse(Reaction.objects.filter(review=self.review, user=self.reactor_1).exists())

    def test_reaction_survives_concurrent_create_race(self):
        """A row created by a racing request mid-check is updated, not a 500."""
        Reaction.objects.create(review=self.review, user=self.reactor_1, emoji='👎')
        self.client.force_login(self.reactor_1)

        with patch.object(Reaction.objects, 'filter') as mock_filter:
            # Simulate the race window: the existence pre-check sees no row even
            # though a concurrent request has already created one.
            mock_filter.return_value.first.return_value = None
            response = self.client.post(reverse('web-review-react', args=[self.review.id]), {'emoji': '👍'})

        self.assertRedirects(
            response,
            reverse('web-recipe-detail', args=[self.recipe.id]),
            fetch_redirect_response=False,
        )
        reaction = Reaction.objects.get(review=self.review, user=self.reactor_1)
        self.assertEqual(reaction.emoji, '👍')

    def test_member_cannot_react_to_review_on_non_public_recipe(self):
        self.recipe.status = Recipe.STATUS_BLOCKED
        self.recipe.save(update_fields=['status'])

        response = self._react(self.reactor_1, '👍')

        self.assertRedirects(response, reverse('web-home'), fetch_redirect_response=False)
        self.assertFalse(Reaction.objects.filter(review=self.review, user=self.reactor_1).exists())

    def test_steward_can_react_to_review_on_non_public_recipe(self):
        steward = make_user(
            role='steward',
            username='reaction-steward',
            email='reaction-steward@example.com',
            first_name='Reaction',
            last_name='Steward',
        )
        self.recipe.status = Recipe.STATUS_BLOCKED
        self.recipe.save(update_fields=['status'])

        response = self._react(steward, '👍')

        self.assertRedirects(
            response,
            reverse('web-recipe-detail', args=[self.recipe.id]),
            fetch_redirect_response=False,
        )
        self.assertEqual(Reaction.objects.filter(review=self.review, user=steward).count(), 1)

    def test_recipe_detail_exposes_reaction_summary_and_viewer_reaction(self):
        Reaction.objects.create(review=self.review, user=self.reactor_1, emoji='👍')
        Reaction.objects.create(review=self.review, user=self.reactor_2, emoji='👍')
        Reaction.objects.create(review=self.review, user=self.author, emoji='👎')

        self.client.force_login(self.reactor_1)
        response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))

        self.assertEqual(response.status_code, 200)
        review = response.context['reviews'][0]
        self.assertIn(('👍', 2), review.reaction_summary)
        self.assertIn(('👎', 1), review.reaction_summary)
        self.assertEqual(review.viewer_reaction, '👍')

    def test_review_list_supports_pagination(self):
        for index in range(12):
            Review.objects.create(
                recipe=self.recipe,
                user=self._create_extra_user(f'page-{index}'),
                rating=4,
                content=f'Extra review {index}',
            )

        response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]), {'review_page': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['review_page'].number, 2)
        self.assertContains(response, 'Page 2 of')

    def test_review_pagination_links_keep_extra_query_params(self):
        for index in range(12):
            Review.objects.create(
                recipe=self.recipe,
                user=self._create_extra_user(f'filter-{index}'),
                rating=4,
                content=f'Paged review {index}',
            )

        response = self.client.get(
            reverse('web-recipe-detail', args=[self.recipe.id]),
            {'focus': 'recent', 'review_page': 2},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'focus=recent&amp;review_page=1')
        self.assertNotContains(response, 'focus=recent&amp;page=1')


class ReactionRateLimitTests(TestCase):
    """Reaction endpoint should enforce configured throttling."""

    def setUp(self):
        cache.clear()
        self.user = make_user(
            username='rate-limit-user',
            email='rate-limit-user@example.com',
            first_name='Rate',
            last_name='Limit',
        )
        self.author = make_user(
            username='rate-reaction-author',
            email='rate-reaction-author@example.com',
            first_name='Rate',
            last_name='Author',
        )
        self.recipe = make_recipe(
            title='Rate Limit Recipe',
            description='rate limit fixture.',
            author=self.author,
        )
        self.review = Review.objects.create(recipe=self.recipe, user=self.author, rating=5, content='Great')

    @override_settings(RATE_LIMITS={'reaction': {'limit': 1, 'window': 60}})
    def test_reaction_rate_limit_blocks_second_reaction(self):
        self.client.force_login(self.user)
        first = self.client.post(reverse('web-review-react', args=[self.review.id]), {'emoji': '👍'}, follow=True)
        second = self.client.post(reverse('web-review-react', args=[self.review.id]), {'emoji': '👎'}, follow=True)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertContains(second, 'Too many reaction requests. Please give it a moment and try again.')
