"""Steward capability and recipe status permission tests."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Recipe
from core.templatetags.ui_copy import to_ui_title


class StewardPermissionTests(TestCase):
    """Steward role should unlock moderation capabilities."""

    def setUp(self):
        self.user_model = get_user_model()
        self.author = self.user_model.objects.create_user(
            username='author',
            email='author@example.com',
            first_name='Author',
            last_name='Cook',
            password='pwd-12345',
        )
        self.viewer = self.user_model.objects.create_user(
            username='viewer',
            email='viewer@example.com',
            first_name='Viewer',
            last_name='Guest',
            password='pwd-12345',
        )
        self.steward = self.user_model.objects.create_steward_user(
            username='steward',
            email='steward@example.com',
            first_name='Steward',
            last_name='Owner',
            password='pwd-12345',
        )
        self.recipe = Recipe.objects.create(
            title='Blocked Recipe',
            description='for permission tests',
            cuisine='Home Style',
            flavor='savory',
            steps=['Step 1'],
            cooking_time=20,
            difficulty='easy',
            nutrition={},
            author=self.author,
            status=Recipe.STATUS_BLOCKED,
        )

    def test_steward_role_has_expected_capabilities(self):
        self.assertTrue(self.steward.is_steward)
        self.assertTrue(self.steward.has_capability(self.user_model.CAPABILITY_VIEW_NON_PUBLIC_RECIPE))
        self.assertTrue(self.steward.has_capability(self.user_model.CAPABILITY_UPDATE_RECIPE_STATUS))
        self.assertTrue(self.steward.has_capability(self.user_model.CAPABILITY_DELETE_ANY_RECIPE))

    def test_regular_user_cannot_view_other_users_non_public_recipe(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))
        self.assertRedirects(response, reverse('web-home'))

    def test_steward_can_view_other_users_non_public_recipe(self):
        self.client.force_login(self.steward)
        response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))
        self.assertEqual(response.status_code, 200)

    def test_steward_can_delete_other_users_recipe(self):
        self.client.force_login(self.steward)
        response = self.client.post(reverse('web-recipe-delete', args=[self.recipe.id]))
        self.assertRedirects(response, reverse('web-home'))
        self.assertFalse(Recipe.objects.filter(id=self.recipe.id).exists())

    def test_regular_user_cannot_update_recipe_status(self):
        self.client.force_login(self.viewer)
        response = self.client.post(reverse('web-recipe-status', args=[self.recipe.id]), {'status': 'published'})
        self.assertRedirects(response, reverse('web-recipe-detail', args=[self.recipe.id]), fetch_redirect_response=False)
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.status, Recipe.STATUS_BLOCKED)

    def test_steward_can_update_recipe_status(self):
        self.client.force_login(self.steward)
        response = self.client.post(reverse('web-recipe-status', args=[self.recipe.id]), {'status': 'published'})
        self.assertRedirects(response, reverse('web-recipe-detail', args=[self.recipe.id]), fetch_redirect_response=False)
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.status, Recipe.STATUS_PUBLISHED)

    def test_author_can_see_own_blocked_recipe_in_home_feed(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse('web-home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, to_ui_title(self.recipe.title))
        self.assertNotIn(self.recipe.id, [item.id for item in response.context['hot_recipes']])

    def test_steward_can_see_blocked_recipe_in_home_feed(self):
        self.client.force_login(self.steward)
        response = self.client.get(reverse('web-home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, to_ui_title(self.recipe.title))
        self.assertNotIn(self.recipe.id, [item.id for item in response.context['hot_recipes']])

    def test_regular_user_cannot_see_other_users_blocked_recipe_in_home_feed(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('web-home'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.recipe.title)
