"""Recipe page and create flow tests."""

from unittest.mock import patch

from django.core.cache import cache
from django.db import DatabaseError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Ingredient, Recipe, Review
from core.templatetags.ui_copy import to_ui_title
from core.tests.utils import (
    force_session_key,
    make_ai_draft_bundle,
    make_recipe,
    make_user,
)
from core.views.pages.recipe import create as recipe_create_actions
from core.views.pages.recipe.detail import (
    VIEWED_RECIPES_SESSION_KEY,
    VIEWED_RECIPES_SESSION_LIMIT,
)
from core.views.pages.recipe.home import (
    SEARCHED_RECIPES_SESSION_KEY,
    SEARCHED_RECIPES_SESSION_LIMIT,
)
from core.views.shared.ai import ai_draft_cache_key, peek_ai_draft_payload
from core.views.shared.idempotency import idempotency_ttl_seconds, inflight_marker


class HomeSearchMetricsTests(TestCase):
    """Search behavior should increment ranking heat metrics consistently."""

    def setUp(self):
        self.author = make_user(
            username='search-author',
            email='search-author@example.com',
            first_name='Search',
            last_name='Author',
        )
        self.matching_recipe = make_recipe(
            title='Tomato Noodles',
            description='Simple noodle recipe.',
            steps=['Boil noodles'],
            author=self.author,
        )
        self.other_recipe = make_recipe(
            title='Ginger Soup',
            description='Warm and comforting.',
            flavor='light',
            steps=['Simmer ingredients'],
            cooking_time=30,
            author=self.author,
        )
        Ingredient.objects.create(recipe=self.matching_recipe, name='Scallion', quantity='2', unit='pc', alternative='')
        Ingredient.objects.create(recipe=self.other_recipe, name='Ginger Root', quantity='30', unit='g', alternative='')

    def test_search_query_increments_search_count_for_returned_results(self):
        self.client.get(reverse('web-home'), {'q': 'Tomato'})
        self.matching_recipe.refresh_from_db()
        self.other_recipe.refresh_from_db()
        self.assertEqual(self.matching_recipe.search_count, 1)
        self.assertEqual(self.other_recipe.search_count, 0)

    def test_search_query_increments_search_count_only_for_current_page_matches(self):
        # 14 new matches + the existing 'Tomato Noodles' = 15 results, spanning two pages of 12.
        for index in range(14):
            make_recipe(
                title=f'Tomato Batch Recipe {index}',
                description='Search heat fixture.',
                steps=['Cook'],
                author=self.author,
            )

        matched_ids = list(Recipe.objects.filter(title__icontains='Tomato').values_list('id', flat=True))
        response = self.client.get(reverse('web-home'), {'q': 'Tomato', 'page': 1})
        self.assertEqual(response.status_code, 200)
        updated_count = Recipe.objects.filter(id__in=matched_ids, search_count=1).count()
        self.assertEqual(updated_count, 12)

        response_page_two = self.client.get(reverse('web-home'), {'q': 'Tomato', 'page': 2})
        self.assertEqual(response_page_two.status_code, 200)
        updated_count_after_second_page = Recipe.objects.filter(id__in=matched_ids, search_count=1).count()
        self.assertEqual(updated_count_after_second_page, len(matched_ids))

    def test_empty_search_does_not_increment_search_count(self):
        self.client.get(reverse('web-home'))
        self.matching_recipe.refresh_from_db()
        self.assertEqual(self.matching_recipe.search_count, 0)

    def test_repeat_search_in_same_session_does_not_double_count(self):
        self.client.get(reverse('web-home'), {'q': 'Tomato'})
        self.client.get(reverse('web-home'), {'q': 'Tomato'})
        self.matching_recipe.refresh_from_db()
        self.assertEqual(self.matching_recipe.search_count, 1)

    def test_new_session_search_counts_again(self):
        self.client.get(reverse('web-home'), {'q': 'Tomato'})
        other_client = Client()
        other_client.get(reverse('web-home'), {'q': 'Tomato'})
        self.matching_recipe.refresh_from_db()
        self.assertEqual(self.matching_recipe.search_count, 2)

    def test_searched_recipes_session_list_is_capped_at_recent_ids(self):
        session = self.client.session
        session[SEARCHED_RECIPES_SESSION_KEY] = list(range(10_000, 10_000 + SEARCHED_RECIPES_SESSION_LIMIT))
        session.save()

        self.client.get(reverse('web-home'), {'q': 'Tomato'})

        self.matching_recipe.refresh_from_db()
        self.assertEqual(self.matching_recipe.search_count, 1)
        kept_ids = self.client.session[SEARCHED_RECIPES_SESSION_KEY]
        self.assertEqual(len(kept_ids), SEARCHED_RECIPES_SESSION_LIMIT)
        self.assertNotIn(10_000, kept_ids)
        self.assertIn(self.matching_recipe.id, kept_ids)

    def test_search_matches_ingredient_names(self):
        response = self.client.get(reverse('web-home'), {'q': 'Scallion'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, to_ui_title(self.matching_recipe.title))
        self.assertEqual([recipe.id for recipe in response.context['recipes']], [self.matching_recipe.id])
        self.matching_recipe.refresh_from_db()
        self.assertEqual(self.matching_recipe.search_count, 1)

    def test_search_matches_recipe_steps_text(self):
        response = self.client.get(reverse('web-home'), {'q': 'Simmer'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, to_ui_title(self.other_recipe.title))
        self.assertEqual([recipe.id for recipe in response.context['recipes']], [self.other_recipe.id])
        self.other_recipe.refresh_from_db()
        self.assertEqual(self.other_recipe.search_count, 1)

    def test_trending_sidebar_is_global_not_limited_by_search_filter(self):
        hot_recipe = make_recipe(
            title='Viral Chili Bowl',
            description='A globally trending recipe.',
            flavor='spicy',
            steps=['Serve hot'],
            cooking_time=15,
            author=self.author,
            view_count=9999,
        )
        response = self.client.get(reverse('web-home'), {'q': 'Tomato'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, hot_recipe.title)

    def test_home_feed_supports_pagination(self):
        # 20 new + 2 setUp recipes = 22 in the feed, nearly filling two pages of 12.
        for index in range(20):
            make_recipe(
                title=f'Paginated Recipe {index}',
                description='Pagination fixture.',
                steps=['Cook'],
                author=self.author,
            )

        response = self.client.get(reverse('web-home'), {'page': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['recipe_page'].number, 2)
        self.assertContains(response, 'Page 2 of')

    def test_home_pagination_links_preserve_active_filters(self):
        # 20 recipes matching the filter = 12 + 8, spanning two pages of 12.
        for index in range(20):
            make_recipe(
                title=f'Filter Recipe {index}',
                description='Pagination filter fixture.',
                steps=['Cook'],
                author=self.author,
            )

        response = self.client.get(reverse('web-home'), {'q': 'Filter', 'sort': 'latest', 'page': 2})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'q=Filter&amp;sort=latest&amp;page=1')

class RecipeOwnershipTests(TestCase):
    """Recipe deletion must remain owner-only."""

    def setUp(self):
        self.author = make_user(
            username='owner-author',
            email='owner-author@example.com',
            first_name='Owner',
            last_name='Author',
        )
        self.viewer = make_user(
            username='owner-viewer',
            email='owner-viewer@example.com',
            first_name='Owner',
            last_name='Viewer',
        )
        self.recipe = make_recipe(
            title='Owner Recipe',
            description='for ownership tests.',
            author=self.author,
        )

    def test_owner_can_delete_recipe(self):
        self.client.force_login(self.author)
        response = self.client.post(reverse('web-recipe-delete', args=[self.recipe.id]))
        self.assertRedirects(response, reverse('web-home'))
        self.assertFalse(Recipe.objects.filter(id=self.recipe.id).exists())

    def test_non_owner_cannot_delete_recipe(self):
        self.client.force_login(self.viewer)
        response = self.client.post(reverse('web-recipe-delete', args=[self.recipe.id]))
        self.assertRedirects(response, reverse('web-recipe-detail', args=[self.recipe.id]), fetch_redirect_response=False)
        self.assertTrue(Recipe.objects.filter(id=self.recipe.id).exists())


class CreateRecipePageTests(TestCase):
    """Create Recipe page behavior and messaging checks."""

    def setUp(self):
        cache.clear()
        self.user = make_user(
            username='create-user',
            email='create-user@example.com',
            first_name='Create',
            last_name='User',
        )
        self.client.force_login(self.user)
        self.session_key = force_session_key(self.client)

    def _build_payload(self, **overrides):
        payload = {
            'title': 'Weeknight Noodles',
            'description': 'Simple and comforting.',
            'cuisine': 'Home Style',
            'flavor': 'savory',
            'cooking_time': 20,
            'difficulty': 'easy',
            'steps_text': '1. Boil noodles\n2. Toss and serve',
            'ingredients_text': 'Noodles,200,g,\nScallion,1,pc,',
        }
        payload.update(overrides)
        return payload

    def _build_ai_draft_bundle(self, *, draft_id='create-prefill-draft'):
        return make_ai_draft_bundle(
            session_key=self.session_key,
            user_id=self.user.id,
            draft_id=draft_id,
            generated_recipe={
                'title': 'AI Weeknight Noodles',
                'description': 'An AI draft ready for editing.',
                'cuisine': 'Home Style',
                'flavor': 'savory',
                'cooking_time': 20,
                'difficulty': 'easy',
                'ingredients': [
                    {'name': 'Noodles', 'quantity': '200', 'unit': 'g', 'alternative': ''},
                    {'name': 'Scallion', 'quantity': '1', 'unit': 'pc', 'alternative': ''},
                ],
                'steps': ['Boil noodles', 'Toss and serve'],
                'nutrition': {},
            },
            source_payload={
                'available_ingredients': ['noodles', 'scallion'],
                'cooking_time': 20,
                'flavor_preference': 'savory',
                'cuisine_preference': 'home style',
                'health_goal': 'balanced',
            },
        )

    def test_create_recipe_publishes_manual_recipe(self):
        response = self.client.post(reverse('web-recipe-create'), self._build_payload(), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your recipe has been published.')
        recipe = Recipe.objects.get(title='Weeknight Noodles')
        self.assertFalse(recipe.is_ai_generated)

    def test_create_recipe_from_ai_draft_keeps_ai_source_metadata(self):
        draft_id, draft_token = self._build_ai_draft_bundle()
        response = self.client.post(
            reverse('web-recipe-create'),
            self._build_payload(
                title='Edited AI Noodles',
                source_draft_id=draft_id,
                source_draft_token=draft_token,
            ),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your recipe has been published.')

        recipe = Recipe.objects.get(title='Edited AI Noodles')
        self.assertTrue(recipe.is_ai_generated)
        self.assertEqual(recipe.source_prompt.get('model'), 'test-model:1')
        self.assertEqual(recipe.source_prompt.get('available_ingredients'), ['noodles', 'scallion'])

    def test_create_recipe_consumes_ai_draft_on_publish(self):
        draft_id, draft_token = self._build_ai_draft_bundle()
        response = self.client.post(
            reverse('web-recipe-create'),
            self._build_payload(
                title='One Shot Noodles',
                source_draft_id=draft_id,
                source_draft_token=draft_token,
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(peek_ai_draft_payload(draft_id))

    def test_create_recipe_rejects_second_use_of_consumed_ai_draft(self):
        draft_id, draft_token = self._build_ai_draft_bundle()
        first = self.client.post(
            reverse('web-recipe-create'),
            self._build_payload(
                title='First Draft Noodles',
                source_draft_id=draft_id,
                source_draft_token=draft_token,
            ),
        )
        self.assertEqual(first.status_code, 302)
        self.assertTrue(Recipe.objects.get(title='First Draft Noodles').is_ai_generated)

        second = self.client.post(
            reverse('web-recipe-create'),
            self._build_payload(
                title='Second Draft Noodles',
                source_draft_id=draft_id,
                source_draft_token=draft_token,
            ),
        )
        self.assertEqual(second.status_code, 200)
        self.assertContains(second, 'That draft is no longer available.')
        self.assertEqual(Recipe.objects.count(), 1)
        self.assertFalse(Recipe.objects.filter(title='Second Draft Noodles').exists())

    def test_create_recipe_rejects_unknown_ai_draft_linkage(self):
        response = self.client.post(
            reverse('web-recipe-create'),
            self._build_payload(
                source_draft_id='missing-draft-id',
                source_draft_token='bogus-token',
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'That draft is no longer available.')
        self.assertEqual(Recipe.objects.count(), 0)

    @patch('core.views.shared.ai.issue_ai_draft')
    @patch('core.views.pages.recipe.create.create_recipe_with_ingredients', side_effect=RuntimeError('db write failure'))
    def test_create_recipe_unexpected_error_propagates_without_reissue(self, _mock_create_recipe, mock_issue_ai_draft):
        # Programming errors still propagate; like the AI studio publish flow,
        # only database errors earn a draft re-issue.
        draft_id, draft_token = self._build_ai_draft_bundle()
        with self.assertRaises(RuntimeError):
            self.client.post(
                reverse('web-recipe-create'),
                self._build_payload(
                    source_draft_id=draft_id,
                    source_draft_token=draft_token,
                ),
            )
        mock_issue_ai_draft.assert_not_called()

    @patch('core.views.shared.ai.issue_ai_draft', return_value=('reissued-draft-id', 'reissued-token'))
    @patch('core.views.pages.recipe.create.create_recipe_with_ingredients', side_effect=DatabaseError('db write failure'))
    def test_create_recipe_database_error_reissues_ai_draft(self, _mock_create_recipe, mock_issue_ai_draft):
        draft_id, draft_token = self._build_ai_draft_bundle()

        response = self.client.post(
            reverse('web-recipe-create'),
            self._build_payload(
                source_draft_id=draft_id,
                source_draft_token=draft_token,
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'We could not save that recipe right now.')
        # The consumed one-time draft was re-issued and the re-bound form
        # carries the new linkage so a retry stays an AI-sourced recipe.
        self.assertContains(response, 'value="reissued-draft-id"')
        self.assertContains(response, 'value="reissued-token"')
        self.assertEqual(Recipe.objects.count(), 0)
        mock_issue_ai_draft.assert_called_once()
        reissued = mock_issue_ai_draft.call_args.kwargs
        self.assertEqual(reissued['generated_recipe']['title'], 'AI Weeknight Noodles')
        self.assertEqual(reissued['source_payload']['available_ingredients'], ['noodles', 'scallion'])
        self.assertEqual(reissued['model'], 'test-model:1')

    def test_create_recipe_with_expired_draft_retries_as_plain_recipe(self):
        draft_id, draft_token = self._build_ai_draft_bundle()
        # Simulate the 30-minute draft TTL expiring before the publish submit.
        cache.delete(ai_draft_cache_key(draft_id))

        first = self.client.post(
            reverse('web-recipe-create'),
            self._build_payload(
                source_draft_id=draft_id,
                source_draft_token=draft_token,
            ),
        )
        self.assertEqual(first.status_code, 200)
        self.assertContains(first, 'That draft is no longer available.')
        self.assertEqual(Recipe.objects.count(), 0)
        # The re-bound form drops the stale hidden linkage so the retry is not
        # trapped in the same unrecoverable error.
        self.assertNotContains(first, f'value="{draft_id}"')

        retry = self.client.post(reverse('web-recipe-create'), self._build_payload())
        self.assertEqual(retry.status_code, 302)
        recipe = Recipe.objects.get(title='Weeknight Noodles')
        self.assertFalse(recipe.is_ai_generated)

    def test_create_recipe_identical_resubmit_with_consumed_draft_redirects_to_recipe(self):
        draft_id, draft_token = self._build_ai_draft_bundle()
        payload = self._build_payload(
            title='Resubmitted Draft Noodles',
            source_draft_id=draft_id,
            source_draft_token=draft_token,
        )

        first = self.client.post(reverse('web-recipe-create'), payload)
        self.assertEqual(first.status_code, 302)
        created = Recipe.objects.get(title='Resubmitted Draft Noodles')

        second = self.client.post(reverse('web-recipe-create'), payload)
        self.assertRedirects(second, reverse('web-recipe-detail', args=[created.id]), fetch_redirect_response=False)
        self.assertEqual(Recipe.objects.count(), 1)

    def test_create_recipe_double_submit_redirects_to_existing_recipe(self):
        payload = self._build_payload()

        first = self.client.post(reverse('web-recipe-create'), payload)
        self.assertEqual(first.status_code, 302)
        created = Recipe.objects.get(title='Weeknight Noodles')
        self.assertEqual(Recipe.objects.count(), 1)

        second = self.client.post(reverse('web-recipe-create'), payload)
        self.assertRedirects(second, reverse('web-recipe-detail', args=[created.id]), fetch_redirect_response=False)
        self.assertEqual(Recipe.objects.count(), 1)

    def test_create_recipe_inflight_marker_blocks_duplicate_submit(self):
        payload = self._build_payload()
        steps = recipe_create_actions.parse_steps(payload['steps_text'])
        ingredients = recipe_create_actions.parse_ingredients(payload['ingredients_text'])
        idempotency_key = recipe_create_actions._recipe_create_idempotency_key(
            user_id=self.user.id,
            base_payload={
                'title': payload['title'],
                'description': payload['description'],
                'cuisine': payload['cuisine'],
                'flavor': payload['flavor'],
                'steps': steps,
                'cooking_time': payload['cooking_time'],
                'difficulty': payload['difficulty'],
                'ingredients': ingredients,
                'nutrition': {},
            },
        )
        cache.set(idempotency_key, inflight_marker(), timeout=idempotency_ttl_seconds('IDEMPOTENCY_RECIPE_CREATE_WINDOW_SECONDS'))

        response = self.client.post(reverse('web-recipe-create'), payload, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'still being processed')
        self.assertEqual(Recipe.objects.count(), 0)

    @override_settings(RATE_LIMITS={'recipe_create': {'limit': 1, 'window': 60}})
    def test_create_recipe_rate_limit_blocks_second_submission(self):
        first_payload = self._build_payload(title='Rate Limit Recipe 1')
        second_payload = self._build_payload(title='Rate Limit Recipe 2')

        first = self.client.post(reverse('web-recipe-create'), first_payload)
        self.assertEqual(first.status_code, 302)
        second = self.client.post(reverse('web-recipe-create'), second_payload)
        self.assertEqual(second.status_code, 200)
        self.assertContains(second, 'Too many recipe publish attempts.')
        self.assertEqual(Recipe.objects.count(), 1)

    @override_settings(RATE_LIMITS={'recipe_create': {'limit': 1, 'window': 60}})
    def test_create_recipe_rate_limit_skips_invalid_submissions(self):
        invalid_payload = self._build_payload(title='')

        first = self.client.post(reverse('web-recipe-create'), invalid_payload)
        self.assertEqual(first.status_code, 200)
        second = self.client.post(reverse('web-recipe-create'), invalid_payload)
        self.assertEqual(second.status_code, 200)
        self.assertNotContains(second, 'Too many recipe publish attempts.')

        valid = self.client.post(reverse('web-recipe-create'), self._build_payload(title='Valid After Invalid'))
        self.assertEqual(valid.status_code, 302)
        self.assertEqual(Recipe.objects.count(), 1)

    @patch('core.views.pages.recipe.create.create_recipe_with_ingredients', side_effect=DatabaseError('db write failure'))
    def test_create_recipe_database_error_without_draft_propagates(self, _mock_create_recipe):
        # No AI draft linkage: a failed save has no consumed draft to re-issue,
        # so the error propagates instead of bouncing the user back to the form.
        with self.assertRaises(DatabaseError):
            self.client.post(reverse('web-recipe-create'), self._build_payload())


class ReviewSubmissionAccessTests(TestCase):
    """Review submission should use the same login interception model as other writes."""

    def setUp(self):
        cache.clear()
        self.author = make_user(
            username='review-author',
            email='review-author@example.com',
            first_name='Review',
            last_name='Author',
        )
        self.reviewer = make_user(
            username='review-member',
            email='review-member@example.com',
            first_name='Review',
            last_name='Member',
        )
        self.recipe = make_recipe(
            title='Reviewable Recipe',
            description='for review submit access tests.',
            author=self.author,
        )

    def test_anonymous_review_submit_redirects_to_login(self):
        response = self.client.post(
            reverse('web-recipe-review', args=[self.recipe.id]),
            {'rating': 5, 'content': 'Great!', 'is_anonymous': False},
        )
        expected = f"{reverse('web-login')}?next={reverse('web-recipe-review', args=[self.recipe.id])}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)
        self.assertEqual(Review.objects.count(), 0)

    def test_member_can_submit_review(self):
        self.client.force_login(self.reviewer)
        response = self.client.post(
            reverse('web-recipe-review', args=[self.recipe.id]),
            {'rating': 5, 'content': 'Great!', 'is_anonymous': False},
        )
        self.assertRedirects(response, reverse('web-recipe-detail', args=[self.recipe.id]), fetch_redirect_response=False)
        self.assertEqual(Review.objects.count(), 1)

    def test_author_cannot_review_own_recipe(self):
        self.client.force_login(self.author)
        response = self.client.post(
            reverse('web-recipe-review', args=[self.recipe.id]),
            {'rating': 5, 'content': 'Great!', 'is_anonymous': False},
        )
        self.assertRedirects(response, reverse('web-recipe-detail', args=[self.recipe.id]), fetch_redirect_response=False)
        self.assertEqual(Review.objects.count(), 0)

    def test_second_review_submission_updates_existing_review(self):
        self.client.force_login(self.reviewer)
        url = reverse('web-recipe-review', args=[self.recipe.id])

        first = self.client.post(url, {'rating': 5, 'content': 'Great!', 'is_anonymous': False})
        self.assertEqual(first.status_code, 302)

        second = self.client.post(url, {'rating': 4, 'content': 'Updated note', 'is_anonymous': True}, follow=True)
        self.assertEqual(second.status_code, 200)
        self.assertContains(second, 'Your earlier note has been updated.')
        self.assertEqual(Review.objects.count(), 1)

        review = Review.objects.get(recipe=self.recipe, user=self.reviewer)
        self.assertEqual(review.rating, 4)
        self.assertEqual(review.content, 'Updated note')
        self.assertTrue(review.is_anonymous)

    @override_settings(RATE_LIMITS={'review_submit': {'limit': 1, 'window': 60}})
    def test_review_submit_rate_limit_blocks_second_submission(self):
        self.client.force_login(self.reviewer)
        url = reverse('web-recipe-review', args=[self.recipe.id])

        first = self.client.post(url, {'rating': 5, 'content': 'Great!', 'is_anonymous': False})
        self.assertEqual(first.status_code, 302)

        second = self.client.post(url, {'rating': 4, 'content': 'Still good!', 'is_anonymous': False}, follow=True)
        self.assertEqual(second.status_code, 200)
        self.assertContains(second, 'Too many note submissions.')
        self.assertEqual(Review.objects.count(), 1)

    @override_settings(RATE_LIMITS={'review_submit': {'limit': 1, 'window': 60}})
    def test_review_submit_rate_limit_skips_invalid_submissions(self):
        self.client.force_login(self.reviewer)
        url = reverse('web-recipe-review', args=[self.recipe.id])
        invalid_payload = {'rating': '', 'content': '', 'is_anonymous': False}

        first = self.client.post(url, invalid_payload, follow=True)
        self.assertContains(first, 'Complete the note before sharing it.')
        second = self.client.post(url, invalid_payload, follow=True)
        self.assertNotContains(second, 'Too many note submissions.')

        valid = self.client.post(url, {'rating': 5, 'content': 'Great!', 'is_anonymous': False})
        self.assertEqual(valid.status_code, 302)
        self.assertEqual(Review.objects.count(), 1)


class ReviewAnonymousStateTests(TestCase):
    """The review form should reflect and honor the viewer's anonymity choice."""

    def setUp(self):
        cache.clear()
        self.author = make_user(
            username='jane-doe',
            email='jane.doe@example.com',
            first_name='Jane',
            last_name='Doe',
        )
        self.reviewer = make_user(
            username='john-doe',
            email='john.doe@example.com',
            first_name='John',
            last_name='Doe',
        )
        self.recipe = make_recipe(
            title='Jane Doe Dumplings',
            description='Anonymous state fixture.',
            author=self.author,
        )

    def test_detail_page_prefills_checked_anonymous_checkbox_for_anonymous_review(self):
        Review.objects.create(
            recipe=self.recipe,
            user=self.reviewer,
            rating=4,
            content='Quiet note.',
            is_anonymous=True,
        )
        self.client.force_login(self.reviewer)

        response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="is_anonymous" id="id_is_anonymous" checked')

    def test_detail_page_leaves_anonymous_checkbox_unchecked_for_public_review(self):
        Review.objects.create(
            recipe=self.recipe,
            user=self.reviewer,
            rating=4,
            content='Public note.',
            is_anonymous=False,
        )
        self.client.force_login(self.reviewer)

        response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="is_anonymous" id="id_is_anonymous" checked')

    def test_resubmission_applies_the_users_current_anonymous_choice(self):
        self.client.force_login(self.reviewer)
        url = reverse('web-recipe-review', args=[self.recipe.id])

        self.client.post(url, {'rating': 5, 'content': 'Great!', 'is_anonymous': 'on'})
        review = Review.objects.get(recipe=self.recipe, user=self.reviewer)
        self.assertTrue(review.is_anonymous)

        # The re-rendered form shows the checkbox checked; deliberately
        # unchecking it before resubmitting is the user's informed choice.
        response = self.client.post(url, {'rating': 4, 'content': 'Still great!'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your earlier note has been updated.')
        review.refresh_from_db()
        self.assertFalse(review.is_anonymous)


class RecipePresentationTests(TestCase):
    """Flavor tags and status badges should follow presentation rules."""

    def setUp(self):
        self.author = make_user(
            username='present-author',
            email='present-author@example.com',
            first_name='Present',
            last_name='Author',
        )
        self.member = make_user(
            username='present-member',
            email='present-member@example.com',
            first_name='Present',
            last_name='Member',
        )
        self.steward = make_user(
            role='steward',
            username='present-steward',
            email='present-steward@example.com',
            first_name='Present',
            last_name='Steward',
        )
        self.published_recipe = make_recipe(
            title='Flavorful Bowl',
            description='Presentation checks.',
            flavor="['savory', 'nutrient-dense']",
            steps=['Cook and serve'],
            author=self.author,
            status=Recipe.STATUS_PUBLISHED,
        )
        self.blocked_recipe = make_recipe(
            title='Blocked Bowl',
            description='Visibility checks.',
            steps=['Cook and serve'],
            author=self.author,
            status=Recipe.STATUS_BLOCKED,
        )

    def test_home_splits_flavor_list_text_into_individual_badges(self):
        response = self.client.get(reverse('web-home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Savory')
        self.assertContains(response, 'Nutrient-dense')
        self.assertNotContains(response, "['savory', 'nutrient-dense']")

    def test_member_does_not_see_status_for_published_recipe(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('web-recipe-detail', args=[self.published_recipe.id]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Status: Published')

    def test_steward_sees_status_for_published_recipe(self):
        self.client.force_login(self.steward)
        response = self.client.get(reverse('web-recipe-detail', args=[self.published_recipe.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Status: Published')

    def test_owner_sees_status_for_non_published_recipe(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse('web-recipe-detail', args=[self.blocked_recipe.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Status: Blocked')

    def test_home_card_tags_keep_priority_and_render_full_source_list(self):
        limited_recipe = make_recipe(
            title='Priority Ladder Recipe',
            description='Tag priority test.',
            flavor='alpha-priority,beta-priority,gamma-priority',
            steps=['Cook and serve'],
            author=self.author,
            status=Recipe.STATUS_BLOCKED,
            is_ai_generated=True,
        )
        self.client.force_login(self.author)

        home_response = self.client.get(reverse('web-home'), {'q': 'Priority Ladder Recipe'})
        self.assertEqual(home_response.status_code, 200)
        self.assertContains(home_response, 'Status: Blocked')
        self.assertContains(home_response, 'AI-assisted')
        self.assertContains(home_response, 'Alpha-priority')
        self.assertContains(home_response, 'Beta-priority')
        self.assertContains(home_response, 'Gamma-priority')
        self.assertContains(home_response, 'badge-more')
        self.assertContains(home_response, '>+0</span>', html=False)

        detail_response = self.client.get(reverse('web-recipe-detail', args=[limited_recipe.id]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, 'Beta-priority')
        self.assertContains(detail_response, 'Gamma-priority')


class TutorialVideoTests(TestCase):
    """Tutorial video links should validate, persist, and render on the detail page."""

    def setUp(self):
        cache.clear()
        self.author = make_user(
            username='video-author',
            email='video-author@example.com',
            first_name='Video',
            last_name='Author',
        )

    def _build_create_payload(self, **overrides):
        payload = {
            'title': 'Video Noodles',
            'description': 'Simple and comforting.',
            'cuisine': 'Home Style',
            'flavor': 'savory',
            'cooking_time': 20,
            'difficulty': 'easy',
            'steps_text': '1. Boil noodles\n2. Toss and serve',
            'ingredients_text': 'Noodles,200,g,',
        }
        payload.update(overrides)
        return payload

    def _create_recipe(self, tutorial_video_url=''):
        return make_recipe(
            title='Video Recipe',
            description='Video fixture.',
            steps=['Cook'],
            author=self.author,
            tutorial_video_url=tutorial_video_url,
        )

    def test_create_recipe_saves_normalized_bilibili_url(self):
        self.client.force_login(self.author)

        response = self.client.post(
            reverse('web-recipe-create'),
            self._build_create_payload(tutorial_video_url='https://m.bilibili.com/video/BV1xx411c7mD?p=2'),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        recipe = Recipe.objects.get(title='Video Noodles')
        self.assertEqual(recipe.tutorial_video_url, 'https://www.bilibili.com/video/BV1xx411c7mD?p=2')

    def test_create_recipe_rejects_malformed_bilibili_url(self):
        self.client.force_login(self.author)

        response = self.client.post(
            reverse('web-recipe-create'),
            self._build_create_payload(tutorial_video_url='https://www.bilibili.com/video/not-a-valid-id'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enter a valid Bilibili video link.')
        self.assertFalse(Recipe.objects.filter(title='Video Noodles').exists())

    def test_create_recipe_allows_non_bilibili_url_as_plain_link(self):
        self.client.force_login(self.author)

        response = self.client.post(
            reverse('web-recipe-create'),
            self._build_create_payload(tutorial_video_url='https://example.com/tutorial'),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        recipe = Recipe.objects.get(title='Video Noodles')
        self.assertEqual(recipe.tutorial_video_url, 'https://example.com/tutorial')

    def test_detail_page_renders_bilibili_embed(self):
        recipe = self._create_recipe('https://www.bilibili.com/video/BV1xx411c7mD')

        response = self.client.get(reverse('web-recipe-detail', args=[recipe.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'https://player.bilibili.com/player.html?bvid=BV1xx411c7mD&amp;page=1')
        self.assertContains(response, 'sandbox="allow-scripts allow-same-origin allow-presentation"')
        self.assertContains(response, 'referrerpolicy="strict-origin-when-cross-origin"')

    def test_detail_page_renders_plain_link_for_non_bilibili_url(self):
        recipe = self._create_recipe('https://example.com/tutorial')

        response = self.client.get(reverse('web-recipe-detail', args=[recipe.id]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<iframe')
        self.assertContains(response, 'href="https://example.com/tutorial"')

    def test_detail_page_hides_video_block_without_url(self):
        recipe = self._create_recipe()

        response = self.client.get(reverse('web-recipe-detail', args=[recipe.id]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'recipe-tutorial-video')

    def test_detail_page_csp_allows_bilibili_player_frames(self):
        recipe = self._create_recipe('https://www.bilibili.com/video/BV1xx411c7mD')

        response = self.client.get(reverse('web-recipe-detail', args=[recipe.id]))

        self.assertEqual(response.status_code, 200)
        self.assertIn('frame-src https://player.bilibili.com', response['Content-Security-Policy'])


class RecipeViewCountTests(TestCase):
    """Detail views should count a recipe at most once per session."""

    def setUp(self):
        self.author = make_user(
            username='view-count-author',
            email='view-count-author@example.com',
            first_name='View',
            last_name='Author',
        )
        self.recipe = make_recipe(
            title='View Count Stew',
            description='View counting checks.',
            steps=['Simmer'],
            author=self.author,
            status=Recipe.STATUS_PUBLISHED,
        )

    def test_first_detail_view_increments_view_count(self):
        response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))
        self.assertEqual(response.status_code, 200)
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.view_count, 1)

    def test_repeat_detail_views_in_same_session_do_not_increment(self):
        self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))
        self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.view_count, 1)

    def test_new_session_counts_another_view(self):
        self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))
        other_client = Client()
        other_client.get(reverse('web-recipe-detail', args=[self.recipe.id]))
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.view_count, 2)

    def test_viewed_recipes_session_list_is_capped_at_recent_ids(self):
        session = self.client.session
        session[VIEWED_RECIPES_SESSION_KEY] = list(range(10_000, 10_000 + VIEWED_RECIPES_SESSION_LIMIT))
        session.save()

        self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))

        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.view_count, 1)
        kept_ids = self.client.session[VIEWED_RECIPES_SESSION_KEY]
        self.assertEqual(len(kept_ids), VIEWED_RECIPES_SESSION_LIMIT)
        self.assertNotIn(10_000, kept_ids)
        self.assertIn(self.recipe.id, kept_ids)
