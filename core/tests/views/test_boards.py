"""Boards page and ranking formula tests."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Recipe, Review
from core.services.rankings import calculate_rankings


class BoardsPageBehaviorTests(TestCase):
    """Boards page should stay read-only and refresh on content changes."""

    def setUp(self):
        cache.clear()
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(
            username='rank-author',
            email='rank-author@example.com',
            first_name='Rank',
            last_name='Author',
            password='pwd-12345',
        )
        Recipe.objects.create(
            title='published recipe',
            description='Used for ranking view checks',
            cuisine='Home Style',
            flavor='savory',
            steps=['Step 1'],
            cooking_time=20,
            difficulty='easy',
            nutrition={},
            author=self.user,
        )

    def test_boards_page_returns_snapshot_context(self):
        response = self.client.get(reverse('web-boards'))
        self.assertEqual(response.status_code, 200)
        ranking = response.context['ranking']
        self.assertEqual(ranking.type, 'red')
        self.assertEqual(ranking.window, 'week')
        self.assertIsInstance(ranking.data, list)
        self.assertEqual(response.context['rank_type'], 'red')
        self.assertEqual(response.context['window'], 'week')
        self.assertContains(response, 'Published Recipe')

    def test_boards_snapshot_cache_is_invalidated_after_recipe_publish(self):
        first = self.client.get(reverse('web-boards'))
        self.assertEqual(first.status_code, 200)
        first_rows = len(first.context['ranking'].data)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse('web-recipe-create'),
            {
                'title': 'Fresh Ranking Candidate',
                'description': 'Newly published for cache invalidation test.',
                'cuisine': 'Home Style',
                'flavor': 'savory',
                'cooking_time': 20,
                'difficulty': 'easy',
                'steps_text': '1. Prep\n2. Cook',
                'ingredients_text': 'Tofu,200,g,',
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        second = self.client.get(reverse('web-boards'))
        self.assertEqual(second.status_code, 200)
        second_rows = len(second.context['ranking'].data)
        self.assertGreaterEqual(second_rows, first_rows + 1)

    def test_boards_section_head_uses_unified_with_side_class(self):
        response = self.client.get(reverse('web-boards'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'section-head with-side')


class RankingFormulaTests(TestCase):
    """Formula-level checks for the simplified ranking heuristics."""

    def setUp(self):
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(
            username='ranking-formula-user',
            email='ranking-formula-user@example.com',
            first_name='Ranking',
            last_name='Formula',
            password='pwd-12345',
        )
        self.reviewer_index = 0

    def _create_recipe(
        self,
        title,
        *,
        view_count=0,
        search_count=0,
        is_ai_generated=False,
        status=Recipe.STATUS_PUBLISHED,
        created_at=None,
    ):
        recipe = Recipe.objects.create(
            title=title,
            description='ranking formula fixture',
            cuisine='Home Style',
            flavor='savory',
            steps=['Step 1'],
            cooking_time=20,
            difficulty='easy',
            nutrition={},
            author=self.user,
            is_ai_generated=is_ai_generated,
            status=status,
            view_count=view_count,
            search_count=search_count,
        )
        if created_at is not None:
            Recipe.objects.filter(pk=recipe.pk).update(created_at=created_at)
            recipe.created_at = created_at
        return recipe

    def _create_review(self, recipe, rating, created_at):
        self.reviewer_index += 1
        reviewer = self.user_model.objects.create_user(
            username=f'ranking-reviewer-{self.reviewer_index}',
            email=f'ranking-reviewer-{self.reviewer_index}@example.com',
            first_name='Ranking',
            last_name=f'Reviewer{self.reviewer_index}',
            password='pwd-12345',
        )
        review = Review.objects.create(
            recipe=recipe,
            user=reviewer,
            rating=rating,
            content='ranking formula review',
        )
        Review.objects.filter(pk=review.pk).update(created_at=created_at)

    def test_red_board_uses_window_reviews_for_rating_and_count(self):
        recipe = self._create_recipe('Windowed Recipe')
        self._create_review(recipe, rating=1, created_at=timezone.now() - timedelta(days=8))
        self._create_review(recipe, rating=5, created_at=timezone.now() - timedelta(hours=2))

        rows = calculate_rankings('red', 'day')
        row = next(item for item in rows if item['recipe_id'] == recipe.id)

        self.assertEqual(row['review_count'], 1)
        self.assertAlmostEqual(row['avg_rating'], 5.0, places=2)

    def test_red_board_prefers_reviewed_recipe_over_unreviewed_heat_spike(self):
        hot_unreviewed = self._create_recipe(
            'Unreviewed but Viral',
            view_count=40000,
            search_count=30000,
        )
        reviewed = self._create_recipe(
            'Reviewed and Solid',
            view_count=260,
            search_count=120,
        )
        for _ in range(3):
            self._create_review(reviewed, rating=5, created_at=timezone.now() - timedelta(hours=3))

        rows = calculate_rankings('red', 'week')
        by_recipe = {item['recipe_id']: item['score'] for item in rows}

        self.assertIn(hot_unreviewed.id, by_recipe)
        self.assertIn(reviewed.id, by_recipe)
        self.assertGreater(by_recipe[reviewed.id], by_recipe[hot_unreviewed.id])

    def test_black_board_surfaces_low_rated_recipe_with_active_reviews(self):
        celebrated = self._create_recipe('Celebrated Dish', view_count=1200, search_count=500)
        debated = self._create_recipe('Debated Dish', view_count=320, search_count=160)
        for _ in range(3):
            self._create_review(celebrated, rating=5, created_at=timezone.now() - timedelta(hours=2))
            self._create_review(debated, rating=1, created_at=timezone.now() - timedelta(hours=2))

        rows = calculate_rankings('black', 'week')
        by_recipe = {item['recipe_id']: item['score'] for item in rows}

        self.assertGreater(by_recipe[debated.id], by_recipe[celebrated.id])

    def test_ai_board_only_lists_ai_generated_recipes(self):
        ai_recipe = self._create_recipe('AI Candidate', is_ai_generated=True)
        human_recipe = self._create_recipe('Human Candidate', is_ai_generated=False)
        self._create_review(ai_recipe, rating=5, created_at=timezone.now() - timedelta(hours=2))
        self._create_review(human_recipe, rating=5, created_at=timezone.now() - timedelta(hours=2))

        rows = calculate_rankings('ai', 'week')
        recipe_ids = {item['recipe_id'] for item in rows}

        self.assertIn(ai_recipe.id, recipe_ids)
        self.assertNotIn(human_recipe.id, recipe_ids)

    def test_blocked_recipes_are_excluded_from_rankings(self):
        published = self._create_recipe('Published Candidate')
        blocked = self._create_recipe('Blocked Candidate', status=Recipe.STATUS_BLOCKED)
        self._create_review(published, rating=4, created_at=timezone.now() - timedelta(hours=2))
        self._create_review(blocked, rating=1, created_at=timezone.now() - timedelta(hours=2))

        rows = calculate_rankings('red', 'week')
        recipe_ids = {item['recipe_id'] for item in rows}

        self.assertIn(published.id, recipe_ids)
        self.assertNotIn(blocked.id, recipe_ids)

    def test_heat_uses_recipe_counters_directly(self):
        cool_recipe = self._create_recipe('Cool Recipe', view_count=50, search_count=20)
        hot_recipe = self._create_recipe('Hot Recipe', view_count=5000, search_count=2600)

        rows = calculate_rankings('red', 'week')
        by_recipe = {item['recipe_id']: item['score'] for item in rows}

        self.assertGreater(by_recipe[hot_recipe.id], by_recipe[cool_recipe.id])

    def test_older_heat_is_softened_for_shorter_windows(self):
        stale_recipe = self._create_recipe(
            'Older Heat',
            view_count=5000,
            search_count=2400,
            created_at=timezone.now() - timedelta(days=10),
        )
        fresh_recipe = self._create_recipe(
            'Fresh Heat',
            view_count=800,
            search_count=300,
            created_at=timezone.now() - timedelta(hours=6),
        )

        rows = calculate_rankings('red', 'day')
        by_recipe = {item['recipe_id']: item['score'] for item in rows}

        self.assertGreater(by_recipe[fresh_recipe.id], by_recipe[stale_recipe.id])

    def test_red_board_caps_review_volume_bonus(self):
        volume_inflated = self._create_recipe('Volume Inflated')
        small_but_excellent = self._create_recipe('Small but Excellent')
        for _ in range(20):
            self._create_review(volume_inflated, rating=3, created_at=timezone.now() - timedelta(hours=2))
        for _ in range(5):
            self._create_review(small_but_excellent, rating=5, created_at=timezone.now() - timedelta(hours=2))

        rows = calculate_rankings('red', 'week')
        by_recipe = {item['recipe_id']: item['score'] for item in rows}

        self.assertGreater(by_recipe[small_but_excellent.id], by_recipe[volume_inflated.id])

    def test_black_board_excludes_recipes_without_reviews(self):
        hot_unreviewed = self._create_recipe('Hot but Unreviewed', view_count=50000, search_count=40000)
        reviewed_flop = self._create_recipe('Reviewed Flop')
        self._create_review(reviewed_flop, rating=1, created_at=timezone.now() - timedelta(hours=2))

        rows = calculate_rankings('black', 'week')
        recipe_ids = {item['recipe_id'] for item in rows}

        self.assertNotIn(hot_unreviewed.id, recipe_ids)
        self.assertIn(reviewed_flop.id, recipe_ids)
