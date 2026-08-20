"""Recipe page and create flow tests."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Ingredient, Recipe, Review
from core.templatetags.ui_copy import to_ui_title
from core.views.pages.recipe import create as recipe_create_actions
from core.views.shared.recipe.form_prefill import RECIPE_CREATE_PREFILL_SESSION_KEY


class HomeSearchMetricsTests(TestCase):
    """Search behavior should increment ranking heat metrics consistently."""

    def setUp(self):
        self.user_model = get_user_model()
        self.author = self.user_model.objects.create_user(
            username='search-author',
            email='search-author@example.com',
            first_name='Search',
            last_name='Author',
            password='pwd-12345',
        )
        self.matching_recipe = Recipe.objects.create(
            title='Tomato Noodles',
            description='Simple noodle recipe.',
            cuisine='Home Style',
            flavor='savory',
            steps=['Boil noodles'],
            cooking_time=20,
            difficulty='easy',
            nutrition={},
            author=self.author,
        )
        self.other_recipe = Recipe.objects.create(
            title='Ginger Soup',
            description='Warm and comforting.',
            cuisine='Home Style',
            flavor='light',
            steps=['Simmer ingredients'],
            cooking_time=30,
            difficulty='easy',
            nutrition={},
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
        for index in range(14):
            Recipe.objects.create(
                title=f'Tomato Batch Recipe {index}',
                description='Search heat fixture.',
                cuisine='Home Style',
                flavor='savory',
                steps=['Cook'],
                cooking_time=20,
                difficulty='easy',
                nutrition={},
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
        hot_recipe = Recipe.objects.create(
            title='Viral Chili Bowl',
            description='A globally trending recipe.',
            cuisine='Home Style',
            flavor='spicy',
            steps=['Serve hot'],
            cooking_time=15,
            difficulty='easy',
            nutrition={},
            author=self.author,
            view_count=9999,
        )
        response = self.client.get(reverse('web-home'), {'q': 'Tomato'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, hot_recipe.title)

    def test_home_feed_supports_pagination(self):
        for index in range(20):
            Recipe.objects.create(
                title=f'Paginated Recipe {index}',
                description='Pagination fixture.',
                cuisine='Home Style',
                flavor='savory',
                steps=['Cook'],
                cooking_time=20,
                difficulty='easy',
                nutrition={},
                author=self.author,
            )

        response = self.client.get(reverse('web-home'), {'page': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['recipe_page'].number, 2)
        self.assertContains(response, 'Page 2 of')

    def test_home_pagination_links_preserve_active_filters(self):
        for index in range(20):
            Recipe.objects.create(
                title=f'Filter Recipe {index}',
                description='Pagination filter fixture.',
                cuisine='Home Style',
                flavor='savory',
                steps=['Cook'],
                cooking_time=20,
                difficulty='easy',
                nutrition={},
                author=self.author,
            )

        response = self.client.get(reverse('web-home'), {'q': 'Filter', 'sort': 'latest', 'page': 2})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'q=Filter&amp;sort=latest&amp;page=1')

    def test_home_section_head_uses_unified_with_side_class(self):
        response = self.client.get(reverse('web-home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'section-head home-head with-side')


class RecipeOwnershipTests(TestCase):
    """Recipe deletion must remain owner-only."""

    def setUp(self):
        self.user_model = get_user_model()
        self.author = self.user_model.objects.create_user(
            username='owner-author',
            email='owner-author@example.com',
            first_name='Owner',
            last_name='Author',
            password='pwd-12345',
        )
        self.viewer = self.user_model.objects.create_user(
            username='owner-viewer',
            email='owner-viewer@example.com',
            first_name='Owner',
            last_name='Viewer',
            password='pwd-12345',
        )
        self.recipe = Recipe.objects.create(
            title='Owner Recipe',
            description='for ownership tests',
            cuisine='Home Style',
            flavor='savory',
            steps=['Step 1'],
            cooking_time=20,
            difficulty='easy',
            nutrition={},
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

    SIGNING_SALT = 'core.ai.draft'

    def setUp(self):
        cache.clear()
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(
            username='create-user',
            email='create-user@example.com',
            first_name='Create',
            last_name='User',
            password='pwd-12345',
        )
        self.client.force_login(self.user)
        session = self.client.session
        session['recipe_create_tests'] = True
        session.save()
        self.session_key = session.session_key

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
        cache.set(
            f'ai-draft:{draft_id}',
            {
                'generated_recipe': {
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
                'source_payload': {
                    'available_ingredients': ['noodles', 'scallion'],
                    'cooking_time': 20,
                    'flavor_preference': 'savory',
                    'cuisine_preference': 'home style',
                    'health_goal': 'balanced',
                },
                'model': 'test-model:1',
            },
            timeout=30 * 60,
        )
        return draft_id, signing.dumps(
            {
                'draft_id': draft_id,
                'session_key': self.session_key,
                'issued_for_user_id': self.user.id,
            },
            salt=self.SIGNING_SALT,
            compress=True,
        )

    def test_create_recipe_publishes_manual_recipe(self):
        response = self.client.post(reverse('web-recipe-create'), self._build_payload(), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your recipe has been shared.')
        recipe = Recipe.objects.get(title='Weeknight Noodles')
        self.assertFalse(recipe.is_ai_generated)

    def test_create_page_loads_ai_draft_prefill_from_session(self):
        session = self.client.session
        session[RECIPE_CREATE_PREFILL_SESSION_KEY] = {
            'title': 'AI Weeknight Noodles',
            'description': 'An AI draft ready for editing.',
            'cuisine': 'Home Style',
            'flavor': 'savory',
            'cooking_time': 20,
            'difficulty': 'easy',
            'steps_text': '1. Boil noodles\n2. Toss and serve',
            'ingredients_text': 'Noodles,200,g,\nScallion,1,pc,',
            'source_draft_id': 'prefill-draft',
            'source_draft_token': 'prefill-token',
        }
        session.save()

        response = self.client.get(f"{reverse('web-recipe-create')}?draft=1")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="AI Weeknight Noodles"')
        self.assertContains(response, 'An AI draft ready for editing.')
        self.assertContains(response, 'name="source_draft_id" value="prefill-draft"')
        self.assertContains(response, 'name="source_draft_token" value="prefill-token"')

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
        self.assertContains(response, 'Your recipe has been shared.')

        recipe = Recipe.objects.get(title='Edited AI Noodles')
        self.assertTrue(recipe.is_ai_generated)
        self.assertEqual(recipe.source_prompt.get('model'), 'test-model:1')
        self.assertEqual(recipe.source_prompt.get('available_ingredients'), ['noodles', 'scallion'])

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
        cache.set(idempotency_key, {'state': 'inflight'}, timeout=45)

        response = self.client.post(reverse('web-recipe-create'), payload, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'still being processed')
        self.assertEqual(Recipe.objects.count(), 0)

    @override_settings(RATE_LIMITS={'recipe_create': {'limit': 1, 'window': 60}})
    def test_create_recipe_rate_limit_blocks_second_submission(self):
        cache.clear()
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
        cache.clear()
        invalid_payload = self._build_payload(title='')

        first = self.client.post(reverse('web-recipe-create'), invalid_payload)
        self.assertEqual(first.status_code, 200)
        second = self.client.post(reverse('web-recipe-create'), invalid_payload)
        self.assertEqual(second.status_code, 200)
        self.assertNotContains(second, 'Too many recipe publish attempts.')

        valid = self.client.post(reverse('web-recipe-create'), self._build_payload(title='Valid After Invalid'))
        self.assertEqual(valid.status_code, 302)
        self.assertEqual(Recipe.objects.count(), 1)

    @patch('core.views.pages.recipe.create.create_recipe_with_ingredients', side_effect=RuntimeError('db write failure'))
    def test_create_recipe_raises_when_unexpected_error_occurs(self, _mock_create_recipe):
        with self.assertRaises(RuntimeError):
            self.client.post(reverse('web-recipe-create'), self._build_payload())


class ReviewSubmissionAccessTests(TestCase):
    """Review submission should use the same login interception model as other writes."""

    def setUp(self):
        self.user_model = get_user_model()
        self.author = self.user_model.objects.create_user(
            username='review-author',
            email='review-author@example.com',
            first_name='Review',
            last_name='Author',
            password='pwd-12345',
        )
        self.reviewer = self.user_model.objects.create_user(
            username='review-member',
            email='review-member@example.com',
            first_name='Review',
            last_name='Member',
            password='pwd-12345',
        )
        self.recipe = Recipe.objects.create(
            title='Reviewable Recipe',
            description='for review submit access tests',
            cuisine='Home Style',
            flavor='savory',
            steps=['Step 1'],
            cooking_time=20,
            difficulty='easy',
            nutrition={},
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
        self.assertContains(second, 'Your earlier review has been updated.')
        self.assertEqual(Review.objects.count(), 1)

        review = Review.objects.get(recipe=self.recipe, user=self.reviewer)
        self.assertEqual(review.rating, 4)
        self.assertEqual(review.content, 'Updated note')
        self.assertTrue(review.is_anonymous)

    @override_settings(RATE_LIMITS={'review_submit': {'limit': 1, 'window': 60}})
    def test_review_submit_rate_limit_blocks_second_submission(self):
        cache.clear()
        self.client.force_login(self.reviewer)
        url = reverse('web-recipe-review', args=[self.recipe.id])

        first = self.client.post(url, {'rating': 5, 'content': 'Great!', 'is_anonymous': False})
        self.assertEqual(first.status_code, 302)

        second = self.client.post(url, {'rating': 4, 'content': 'Still good!', 'is_anonymous': False}, follow=True)
        self.assertEqual(second.status_code, 200)
        self.assertContains(second, 'Too many review submissions.')
        self.assertEqual(Review.objects.count(), 1)

    @override_settings(RATE_LIMITS={'review_submit': {'limit': 1, 'window': 60}})
    def test_review_submit_rate_limit_skips_invalid_submissions(self):
        cache.clear()
        self.client.force_login(self.reviewer)
        url = reverse('web-recipe-review', args=[self.recipe.id])
        invalid_payload = {'rating': '', 'content': '', 'is_anonymous': False}

        first = self.client.post(url, invalid_payload, follow=True)
        self.assertContains(first, 'Complete the review before sharing it.')
        second = self.client.post(url, invalid_payload, follow=True)
        self.assertNotContains(second, 'Too many review submissions.')

        valid = self.client.post(url, {'rating': 5, 'content': 'Great!', 'is_anonymous': False})
        self.assertEqual(valid.status_code, 302)
        self.assertEqual(Review.objects.count(), 1)


class RecipePresentationTests(TestCase):
    """Flavor tags and status badges should follow presentation rules."""

    def setUp(self):
        self.user_model = get_user_model()
        self.author = self.user_model.objects.create_user(
            username='present-author',
            email='present-author@example.com',
            first_name='Present',
            last_name='Author',
            password='pwd-12345',
        )
        self.member = self.user_model.objects.create_user(
            username='present-member',
            email='present-member@example.com',
            first_name='Present',
            last_name='Member',
            password='pwd-12345',
        )
        self.steward = self.user_model.objects.create_steward_user(
            username='present-steward',
            email='present-steward@example.com',
            first_name='Present',
            last_name='Steward',
            password='pwd-12345',
        )
        self.published_recipe = Recipe.objects.create(
            title='Flavorful Bowl',
            description='Presentation checks.',
            cuisine='Home Style',
            flavor="['savory', 'nutrient-dense']",
            steps=['Cook and serve'],
            cooking_time=20,
            difficulty='easy',
            nutrition={},
            author=self.author,
            status=Recipe.STATUS_PUBLISHED,
        )
        self.blocked_recipe = Recipe.objects.create(
            title='Blocked Bowl',
            description='Visibility checks.',
            cuisine='Home Style',
            flavor='savory',
            steps=['Cook and serve'],
            cooking_time=20,
            difficulty='easy',
            nutrition={},
            author=self.author,
            status=Recipe.STATUS_BLOCKED,
        )

    def test_home_splits_flavor_list_text_into_individual_badges(self):
        response = self.client.get(reverse('web-home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'SAVORY')
        self.assertContains(response, 'NUTRIENT-DENSE')
        self.assertNotContains(response, "['savory', 'nutrient-dense']")

    def test_member_does_not_see_status_for_published_recipe(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('web-recipe-detail', args=[self.published_recipe.id]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'STATUS: PUBLISHED')

    def test_steward_sees_status_for_published_recipe(self):
        self.client.force_login(self.steward)
        response = self.client.get(reverse('web-recipe-detail', args=[self.published_recipe.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'STATUS: PUBLISHED')

    def test_owner_sees_status_for_non_published_recipe(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse('web-recipe-detail', args=[self.blocked_recipe.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'STATUS: BLOCKED')

    def test_home_card_tags_keep_priority_and_render_full_source_list(self):
        limited_recipe = Recipe.objects.create(
            title='Priority Ladder Recipe',
            description='Tag priority test.',
            cuisine='Home Style',
            flavor='alpha-priority,beta-priority,gamma-priority',
            steps=['Cook and serve'],
            cooking_time=20,
            difficulty='easy',
            nutrition={},
            author=self.author,
            status=Recipe.STATUS_BLOCKED,
            is_ai_generated=True,
        )
        self.client.force_login(self.author)

        home_response = self.client.get(reverse('web-home'), {'q': 'Priority Ladder Recipe'})
        self.assertEqual(home_response.status_code, 200)
        self.assertContains(home_response, 'STATUS: BLOCKED')
        self.assertContains(home_response, 'AI ASSISTED')
        self.assertContains(home_response, 'ALPHA-PRIORITY')
        self.assertContains(home_response, 'BETA-PRIORITY')
        self.assertContains(home_response, 'GAMMA-PRIORITY')
        self.assertContains(home_response, 'badge-more')
        self.assertContains(home_response, '>+0</span>', html=False)

        detail_response = self.client.get(reverse('web-recipe-detail', args=[limited_recipe.id]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, 'BETA-PRIORITY')
        self.assertContains(detail_response, 'GAMMA-PRIORITY')
