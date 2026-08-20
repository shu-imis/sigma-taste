"""AI generation and publish flow tests."""

import secrets
from unittest.mock import Mock, call, patch

import requests
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Recipe, UserPreference
from core.services.ai import OllamaError, list_available_models, resolve_model_name
from core.services.ai.ollama_client import _chat_with_ollama
from core.views.pages.ai import studio as ai_actions


class AIDraftSecurityTests(TestCase):
    """Security and integrity checks for AI draft publishing."""

    SIGNING_SALT = 'core.ai.draft'

    def setUp(self):
        cache.clear()
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(
            username='cooker',
            email='cooker@example.com',
            first_name='Cook',
            last_name='User',
            password='pwd-12345',
        )
        self.client.force_login(self.user)
        session = self.client.session
        session['draft_security'] = True
        session.save()
        self.session_key = session.session_key

    def _build_valid_draft_bundle(self, *, session_key=None, issued_for_user_id=None):
        effective_session_key = session_key or self.session_key
        effective_user_id = self.user.id if issued_for_user_id is None else issued_for_user_id
        draft_id = secrets.token_urlsafe(24)
        cache.set(
            f'ai-draft:{draft_id}',
            {
                'generated_recipe': {
                    'title': 'Signed Stir-Fry',
                    'description': 'A verified AI draft.',
                    'cuisine': 'Home Style',
                    'flavor': 'savory',
                    'cooking_time': 15,
                    'difficulty': 'easy',
                    'ingredients': [
                        {'name': 'Tofu', 'quantity': '200', 'unit': 'g', 'alternative': ''},
                        {'name': 'Pepper', 'quantity': '1', 'unit': 'pc', 'alternative': ''},
                    ],
                    'steps': ['Prep ingredients', 'Stir-fry and serve'],
                    'nutrition': {'calories': 'Approx. 300 kcal'},
                },
                'source_payload': {
                    'available_ingredients': ['tofu', 'pepper'],
                    'cooking_time': 15,
                    'flavor_preference': 'savory',
                    'cuisine_preference': 'home style',
                    'health_goal': 'balanced',
                },
                'model': 'test-model:1',
            },
            timeout=30 * 60,
        )
        payload = {
            'draft_id': draft_id,
            'session_key': effective_session_key,
            'issued_for_user_id': effective_user_id,
        }
        draft_token = signing.dumps(payload, salt=self.SIGNING_SALT, compress=True)
        return draft_id, draft_token

    def test_publish_generated_rejects_tampered_token(self):
        response = self.client.post(
            reverse('web-ai-generate'),
            {
                'action': 'publish_generated',
                'draft_id': 'invalid-id',
                'draft_token': 'tampered-token',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no longer available')
        self.assertEqual(Recipe.objects.count(), 0)

    def test_publish_generated_accepts_signed_token(self):
        draft_id, draft_token = self._build_valid_draft_bundle()
        response = self.client.post(
            reverse('web-ai-generate'),
            {
                'action': 'publish_generated',
                'draft_id': draft_id,
                'draft_token': draft_token,
            },
        )
        recipe = Recipe.objects.get(title='Signed Stir-Fry')
        self.assertRedirects(response, reverse('web-recipe-detail', args=[recipe.id]), fetch_redirect_response=False)
        self.assertTrue(recipe.is_ai_generated)
        self.assertEqual(recipe.author_id, self.user.id)
        self.assertEqual(recipe.ingredients.count(), 2)
        self.assertIsNone(cache.get(f'ai-draft:{draft_id}'))

    def test_publish_generated_rejects_token_issued_for_different_user(self):
        other_user = self.user_model.objects.create_user(
            username='other-cooker',
            email='other-cooker@example.com',
            first_name='Other',
            last_name='Cook',
            password='pwd-12345',
        )
        self.client.force_login(other_user)
        session = self.client.session
        session['draft_security_other'] = True
        session.save()

        draft_id, draft_token = self._build_valid_draft_bundle(
            session_key=session.session_key,
            issued_for_user_id=self.user.id,
        )
        response = self.client.post(
            reverse('web-ai-generate'),
            {
                'action': 'publish_generated',
                'draft_id': draft_id,
                'draft_token': draft_token,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no longer available')
        self.assertFalse(Recipe.objects.filter(title='Signed Stir-Fry').exists())

    def test_publish_generated_replay_with_same_draft_is_rejected(self):
        draft_id, draft_token = self._build_valid_draft_bundle()

        first_response = self.client.post(
            reverse('web-ai-generate'),
            {
                'action': 'publish_generated',
                'draft_id': draft_id,
                'draft_token': draft_token,
            },
        )
        recipe = Recipe.objects.get(title='Signed Stir-Fry')
        self.assertRedirects(first_response, reverse('web-recipe-detail', args=[recipe.id]), fetch_redirect_response=False)

        second_response = self.client.post(
            reverse('web-ai-generate'),
            {
                'action': 'publish_generated',
                'draft_id': draft_id,
                'draft_token': draft_token,
            },
        )
        self.assertEqual(second_response.status_code, 200)
        self.assertContains(second_response, 'no longer available')
        self.assertEqual(Recipe.objects.count(), 1)

    def test_continue_editing_redirects_to_recipe_studio_with_prefill(self):
        draft_id, draft_token = self._build_valid_draft_bundle()
        response = self.client.post(
            reverse('web-ai-generate'),
            {
                'action': 'continue_editing',
                'draft_id': draft_id,
                'draft_token': draft_token,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your AI draft is ready to refine in Recipe Studio.')
        self.assertContains(response, 'value="Signed Stir-Fry"')
        self.assertContains(response, 'A verified AI draft.')
        self.assertContains(response, f'name="source_draft_id" value="{draft_id}"')
        self.assertContains(response, 'name="source_draft_token"')

    @override_settings(RATE_LIMITS={'ai_publish': {'limit': 1, 'window': 60}})
    def test_publish_rate_limit_keeps_current_draft_visible(self):
        self.client.post(
            reverse('web-ai-generate'),
            {
                'action': 'publish_generated',
                'draft_id': 'invalid-draft-id',
                'draft_token': 'invalid-draft-token',
            },
        )

        draft_id, draft_token = self._build_valid_draft_bundle()
        response = self.client.post(
            reverse('web-ai-generate'),
            {
                'action': 'publish_generated',
                'draft_id': draft_id,
                'draft_token': draft_token,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Too many publish attempts.')
        self.assertContains(response, '>AI Draft</span>', html=False)
        self.assertContains(response, '>Easy</span>', html=False)
        self.assertContains(response, 'Signed Stir-Fry')
        self.assertContains(response, 'SAVE TO MY RECIPE BOX')

    @patch('core.views.pages.ai.studio.create_recipe_with_ingredients', side_effect=RuntimeError('db write failure'))
    def test_publish_generated_raises_when_unexpected_error_occurs(self, _mock_create_recipe):
        draft_id, draft_token = self._build_valid_draft_bundle()

        with self.assertRaises(RuntimeError):
            self.client.post(
                reverse('web-ai-generate'),
                {
                    'action': 'publish_generated',
                    'draft_id': draft_id,
                    'draft_token': draft_token,
                },
            )

    @patch('core.views.pages.ai.studio.issue_ai_draft', return_value=('reissued-draft-id', 'reissued-token'))
    @patch('core.views.pages.ai.studio.create_recipe_with_ingredients', side_effect=RuntimeError('db write failure'))
    def test_publish_generated_reissues_draft_when_save_fails(self, _mock_create_recipe, mock_issue_ai_draft):
        draft_id, draft_token = self._build_valid_draft_bundle()

        with self.assertRaises(RuntimeError):
            self.client.post(
                reverse('web-ai-generate'),
                {
                    'action': 'publish_generated',
                    'draft_id': draft_id,
                    'draft_token': draft_token,
                },
            )

        mock_issue_ai_draft.assert_called_once()
        reissued = mock_issue_ai_draft.call_args.kwargs
        self.assertEqual(reissued['generated_recipe']['title'], 'Signed Stir-Fry')
        self.assertEqual(reissued['source_payload']['model'], 'test-model:1')
        self.assertEqual(reissued['model'], 'test-model:1')


class AIAnonymousAccessTests(TestCase):
    """Anonymous users should not be able to use AI preview actions."""

    def _payload(self, **overrides):
        payload = {
            'model': 'test-model:1',
            'available_ingredients': 'egg, tomato',
            'cooking_time': 20,
            'flavor_preference': 'savory',
            'cuisine_preference': 'home style',
            'health_goal': 'balanced',
        }
        payload.update(overrides)
        return payload

    @patch('core.views.pages.ai.studio.generate_recipe')
    def test_anonymous_user_cannot_post_generate_preview(self, mock_generate):
        response = self.client.post(reverse('web-ai-generate'), self._payload())
        expected = f"{reverse('web-login')}?next={reverse('web-ai-generate')}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)
        mock_generate.assert_not_called()

    def test_anonymous_user_cannot_open_ai_page(self):
        response = self.client.get(reverse('web-ai-generate'))
        expected = f"{reverse('web-login')}?next={reverse('web-ai-generate')}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)


class AIGenerateErrorMessageTests(TestCase):
    """User-facing AI errors should not expose internal exception details."""

    def setUp(self):
        cache.clear()
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(
            username='ai-errors-user',
            email='ai-errors-user@example.com',
            first_name='Ai',
            last_name='Errors',
            password='pwd-12345',
        )
        self.client.force_login(self.user)

    def _payload(self, **overrides):
        payload = {
            'model': 'test-model:1',
            'available_ingredients': 'egg, tomato',
            'cooking_time': 20,
            'flavor_preference': 'savory',
            'cuisine_preference': 'home style',
            'health_goal': 'balanced',
        }
        payload.update(overrides)
        return payload

    @patch('core.views.pages.ai.studio.resolve_model_name', side_effect=OllamaError('connection refused'))
    def test_model_resolution_error_is_sanitized(self, _mock_resolve_model_name):
        response = self.client.post(reverse('web-ai-generate'), self._payload())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose an available local model to continue.')
        self.assertNotContains(response, 'connection refused')

    @patch('core.views.pages.ai.studio.resolve_model_name', return_value='test-model:1')
    @patch('core.views.pages.ai.studio.generate_recipe', side_effect=OllamaError('socket timeout'))
    def test_generation_error_is_sanitized(self, _mock_generate_recipe, _mock_resolve_model_name):
        response = self.client.post(reverse('web-ai-generate'), self._payload())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'AI recipe generation is unavailable right now. Please try again shortly.')
        self.assertNotContains(response, 'socket timeout')


class AIGenerateDefaultModelSelectionTests(TestCase):
    """AI page model input should follow detected local model availability."""

    def setUp(self):
        cache.clear()
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(
            username='ai-default-model-user',
            email='ai-default-model-user@example.com',
            first_name='Ai',
            last_name='DefaultModel',
            password='pwd-12345',
        )
        self.client.force_login(self.user)

    def _payload(self, **overrides):
        payload = {
            'model': 'qwen2.5:7b',
            'available_ingredients': 'egg, tomato',
            'cooking_time': 20,
            'flavor_preference': 'savory',
            'cuisine_preference': 'home style',
            'health_goal': 'balanced',
        }
        payload.update(overrides)
        return payload

    @patch('core.views.pages.ai.studio.list_available_models', return_value=['qwen2.5:7b', 'llama3.1:8b'])
    def test_ai_page_prefills_first_detected_model(self, _mock_list_available_models):
        response = self.client.get(reverse('web-ai-generate'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<select name="model"', html=False)
        self.assertContains(response, 'option value="qwen2.5:7b" selected', html=False)
        self.assertContains(response, '>qwen2.5:7b</option>', html=False)
        self.assertContains(response, '<option value="llama3.1:8b">llama3.1:8b</option>', html=False)

    @patch('core.views.pages.ai.studio.list_available_models', return_value=['qwen2.5:7b'])
    def test_ai_page_prefills_profile_preferences_into_empty_form(self, _mock_list_available_models):
        UserPreference.objects.create(
            user=self.user,
            spicy=True,
            sour=True,
            allergies='peanuts, shrimp',
            preferred_cuisines='home-style, mediterranean',
            health_goal='lose',
        )

        response = self.client.get(reverse('web-ai-generate'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="flavor_preference" value="spicy, sour"')
        self.assertContains(response, 'name="cuisine_preference" value="home-style"')
        self.assertContains(response, 'name="health_goal" value="Weight loss"')
        self.assertContains(response, 'name="allergies" value="peanuts, shrimp"')

    @patch('core.views.pages.ai.studio.list_available_models', return_value=['qwen2.5:7b'])
    @patch('core.views.pages.ai.studio.issue_ai_draft', return_value=('draft-id', 'signed-token'))
    @patch('core.views.pages.ai.studio.generate_recipe')
    @patch('core.views.pages.ai.studio.resolve_model_name', return_value='qwen2.5:7b')
    def test_ai_generation_payload_carries_allergies_context(
        self,
        _mock_resolve_model_name,
        mock_generate_recipe,
        _mock_issue_ai_draft,
        _mock_list_available_models,
    ):
        mock_generate_recipe.return_value = {
            'title': 'Allergy Aware Recipe',
            'description': 'Generated with allergy context.',
            'cuisine': 'Home Style',
            'flavor': 'savory',
            'cooking_time': 20,
            'difficulty': 'easy',
            'ingredients': [{'name': 'egg', 'quantity': '2', 'unit': 'pc', 'alternative': ''}],
            'steps': ['Cook and serve'],
            'nutrition': {},
        }

        response = self.client.post(
            reverse('web-ai-generate'),
            self._payload(allergies='peanuts, shrimp'),
        )
        self.assertEqual(response.status_code, 200)
        called_payload = mock_generate_recipe.call_args.args[0]
        self.assertEqual(called_payload['allergies'], 'peanuts, shrimp')

    @patch('core.views.pages.ai.studio.list_available_models', return_value=[])
    def test_ai_page_leaves_model_input_blank_when_no_models_detected(self, _mock_list_available_models):
        response = self.client.get(reverse('web-ai-generate'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<select name="model"', html=False)
        self.assertContains(response, 'disabled="disabled"', html=False)
        self.assertContains(response, '>Unavailable</option>', html=False)
        self.assertContains(response, 'No local model is ready yet. Pull or enable one in Ollama to continue.')

    @patch('core.views.pages.ai.studio.list_available_models', return_value=['qwen2.5:7b', 'llama3.1:8b'])
    def test_ai_page_prefills_session_selected_model_when_still_available(self, _mock_list_available_models):
        session = self.client.session
        session['ai:selected_model:v1'] = 'llama3.1:8b'
        session.save()

        response = self.client.get(reverse('web-ai-generate'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'option value="llama3.1:8b" selected', html=False)

    @patch('core.views.pages.ai.studio.list_available_models', return_value=['qwen2.5:7b'])
    @patch('core.views.pages.ai.studio.issue_ai_draft', return_value=('draft-id-1', 'signed-token-1'))
    @patch('core.views.pages.ai.studio.peek_ai_draft_payload', return_value={'generated_recipe': {'title': 'Cached'}})
    @patch('core.views.pages.ai.studio.generate_recipe')
    @patch('core.views.pages.ai.studio.resolve_model_name', return_value='qwen2.5:7b')
    def test_duplicate_generate_request_reuses_recent_cached_draft(
        self,
        _mock_resolve_model_name,
        mock_generate_recipe,
        _mock_peek_draft,
        mock_issue_ai_draft,
        _mock_list_available_models,
    ):
        mock_generate_recipe.return_value = {
            'title': 'Cached Draft Recipe',
            'description': 'Generated once and reused within idempotency window.',
            'cuisine': 'Home Style',
            'flavor': 'savory',
            'cooking_time': 20,
            'difficulty': 'easy',
            'ingredients': [{'name': 'egg', 'quantity': '2', 'unit': 'pc', 'alternative': ''}],
            'steps': ['Cook and serve'],
            'nutrition': {},
        }

        first = self.client.post(reverse('web-ai-generate'), self._payload())
        self.assertEqual(first.status_code, 200)
        self.assertContains(first, '>AI Draft</span>', html=False)
        self.assertContains(first, '>Easy</span>', html=False)
        self.assertContains(first, 'Cached Draft Recipe')
        self.assertContains(first, 'value="draft-id-1"')

        second = self.client.post(reverse('web-ai-generate'), self._payload())
        self.assertEqual(second.status_code, 200)
        self.assertContains(second, 'We reopened the most recent AI draft for this request.')
        self.assertContains(second, '>AI Draft</span>', html=False)
        self.assertContains(second, 'Cached Draft Recipe')
        self.assertContains(second, 'value="draft-id-1"')

        mock_generate_recipe.assert_called_once()
        mock_issue_ai_draft.assert_called_once()

    @patch('core.views.pages.ai.studio.list_available_models', return_value=['qwen2.5:7b'])
    @patch('core.views.pages.ai.studio.generate_recipe')
    @patch('core.views.pages.ai.studio.resolve_model_name', return_value='qwen2.5:7b')
    def test_duplicate_generate_while_inflight_shows_wait_message(
        self,
        _mock_resolve_model_name,
        mock_generate_recipe,
        _mock_list_available_models,
    ):
        session_key = self.client.session.session_key or ''
        inflight_key = ai_actions._ai_generate_idempotency_key(
            user_id=self.user.id,
            session_key=session_key,
            selected_model='qwen2.5:7b',
            payload={
                'available_ingredients': ['egg', 'tomato'],
                'cooking_time': 20,
                'flavor_preference': 'savory',
                'cuisine_preference': 'home style',
                'health_goal': 'balanced',
            },
        )
        cache.set(inflight_key, {'state': 'inflight'}, timeout=45)

        response = self.client.post(reverse('web-ai-generate'), self._payload())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your previous AI generation is still running. Please give it a moment.')
        mock_generate_recipe.assert_not_called()

    @patch('core.views.pages.ai.studio.list_available_models', return_value=['qwen2.5:7b'])
    @patch('core.views.pages.ai.studio.issue_ai_draft', return_value=('draft-id', 'signed-token'))
    @patch('core.views.pages.ai.studio.generate_recipe')
    @patch('core.views.pages.ai.studio.resolve_model_name', return_value='qwen2.5:7b')
    def test_generate_parses_available_ingredients_from_commas_and_newlines(
        self,
        _mock_resolve_model_name,
        mock_generate_recipe,
        _mock_issue_ai_draft,
        _mock_list_available_models,
    ):
        mock_generate_recipe.return_value = {
            'title': 'Parsed Ingredient Recipe',
            'description': 'Generated with normalized ingredient list.',
            'cuisine': 'Home Style',
            'flavor': 'savory',
            'cooking_time': 20,
            'difficulty': 'easy',
            'ingredients': [{'name': 'egg', 'quantity': '2', 'unit': 'pc', 'alternative': ''}],
            'steps': ['Cook and serve'],
            'nutrition': {},
        }

        response = self.client.post(
            reverse('web-ai-generate'),
            self._payload(available_ingredients='egg, tomato\negg；scallion， basil\r\ntomato'),
        )
        self.assertEqual(response.status_code, 200)
        called_payload = mock_generate_recipe.call_args.args[0]
        self.assertEqual(
            called_payload['available_ingredients'],
            ['egg', 'tomato', 'scallion', 'basil'],
        )

    @patch('core.views.pages.ai.studio.list_available_models', return_value=['qwen2.5:7b'])
    @patch('core.views.pages.ai.studio.issue_ai_draft', return_value=('draft-id', 'signed-token'))
    @patch('core.views.pages.ai.studio.generate_recipe')
    @patch('core.views.pages.ai.studio.resolve_model_name', return_value='qwen2.5:7b')
    def test_generate_parses_bulleted_or_numbered_ingredient_lines(
        self,
        _mock_resolve_model_name,
        mock_generate_recipe,
        _mock_issue_ai_draft,
        _mock_list_available_models,
    ):
        mock_generate_recipe.return_value = {
            'title': 'Bullet List Ingredient Recipe',
            'description': 'Generated from bulleted ingredient input.',
            'cuisine': 'Home Style',
            'flavor': 'savory',
            'cooking_time': 20,
            'difficulty': 'easy',
            'ingredients': [{'name': 'egg', 'quantity': '2', 'unit': 'pc', 'alternative': ''}],
            'steps': ['Cook and serve'],
            'nutrition': {},
        }

        response = self.client.post(
            reverse('web-ai-generate'),
            self._payload(available_ingredients='1. egg\n2) tomato\n- basil\n• scallion\n* garlic'),
        )
        self.assertEqual(response.status_code, 200)
        called_payload = mock_generate_recipe.call_args.args[0]
        self.assertEqual(
            called_payload['available_ingredients'],
            ['egg', 'tomato', 'basil', 'scallion', 'garlic'],
        )

    def test_invalid_ai_form_renders_error_messages(self):
        response = self.client.post(
            reverse('web-ai-generate'),
            self._payload(cooking_time=999),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-feedback-kind="form-error"')
        self.assertContains(response, 'Ensure this value is less than or equal to 240.')

    @patch('core.views.pages.ai.studio.list_available_models', return_value=['qwen2.5:7b'])
    @patch('core.views.pages.ai.studio.generate_recipe')
    def test_generate_rejects_model_not_in_available_list(self, mock_generate_recipe, _mock_list_available_models):
        response = self.client.post(reverse('web-ai-generate'), self._payload(model='unlisted-model:1'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose an available local model to continue.')
        mock_generate_recipe.assert_not_called()

    @patch('core.views.pages.ai.studio.consume_rate_limit', side_effect=AssertionError('should not rate-limit set_model'))
    @patch('core.views.pages.ai.studio.list_available_models', return_value=['qwen2.5:7b', 'llama3.1:8b'])
    def test_set_model_action_confirms_valid_model_without_generation(
        self,
        _mock_list_available_models,
        _mock_consume_rate_limit,
    ):
        payload = {
            'action': 'set_model',
            'model': 'llama3.1:8b',
            'available_ingredients': 'egg, tomato',
            'cooking_time': '30',
            'flavor_preference': 'savory',
            'cuisine_preference': 'home style',
            'health_goal': 'balanced',
        }
        response = self.client.post(
            reverse('web-ai-generate'),
            payload,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This model is ready to use.')
        self.assertContains(response, 'option value="llama3.1:8b" selected', html=False)
        self.assertContains(response, 'egg, tomato')
        self.assertContains(response, 'name="cooking_time" value="30"')
        self.assertContains(response, 'name="flavor_preference" value="savory"')
        self.assertEqual(self.client.session.get('ai:selected_model:v1'), 'llama3.1:8b')

    @patch('core.views.pages.ai.studio.consume_rate_limit', side_effect=AssertionError('should not rate-limit set_model'))
    @patch('core.views.pages.ai.studio.list_available_models')
    def test_set_model_action_refreshes_model_list_before_validation(
        self,
        mock_list_available_models,
        _mock_consume_rate_limit,
    ):
        mock_list_available_models.side_effect = [
            ['qwen2.5:7b', 'llama3.1:8b'],
            ['qwen2.5:7b', 'llama3.1:8b'],
        ]
        response = self.client.post(
            reverse('web-ai-generate'),
            {'action': 'set_model', 'model': 'qwen2.5:7b'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(mock_list_available_models.call_args_list), 2)
        self.assertEqual(mock_list_available_models.call_args_list[0], call())
        self.assertEqual(mock_list_available_models.call_args_list[1], call(refresh=True))

    @patch('core.views.pages.ai.studio.list_available_models', return_value=['qwen2.5:7b'])
    def test_set_model_action_rejects_unknown_model(self, _mock_list_available_models):
        response = self.client.post(
            reverse('web-ai-generate'),
            {'action': 'set_model', 'model': 'invalid-model:1'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose an available local model to continue.')

    def test_set_model_action_requires_non_empty_model(self):
        response = self.client.post(
            reverse('web-ai-generate'),
            {'action': 'set_model', 'model': ''},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose a model before continuing.')


class OllamaModelListCachingTests(TestCase):
    """Ollama model discovery should use short-lived cache between requests."""

    def setUp(self):
        cache.clear()

    @override_settings(OLLAMA_MODEL_LIST_CACHE_TTL=60)
    @patch('core.services.ai.ollama_client.requests.get')
    def test_model_list_is_cached_after_first_successful_fetch(self, mock_get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {'models': [{'model': 'deepseek-r1:14b'}]}
        mock_get.return_value = response

        first = list_available_models()
        second = list_available_models()

        self.assertEqual(first, ['deepseek-r1:14b'])
        self.assertEqual(second, ['deepseek-r1:14b'])
        self.assertEqual(mock_get.call_count, 1)

    @override_settings(OLLAMA_MODEL_LIST_CACHE_TTL=60, OLLAMA_MODEL_LIST_NEGATIVE_CACHE_TTL=5)
    @patch('core.services.ai.ollama_client.cache.set')
    @patch('core.services.ai.ollama_client.requests.get', side_effect=requests.RequestException('offline'))
    def test_model_list_failure_uses_short_negative_cache_ttl(self, _mock_get, mock_cache_set):
        models = list_available_models()

        self.assertEqual(models, [])
        mock_cache_set.assert_called_once_with('ollama:available_models:v1', [], timeout=5)

    @patch('core.services.ai.ollama_client.requests.get')
    def test_model_list_tolerates_null_models_member(self, mock_get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {'models': None}
        mock_get.return_value = response

        self.assertEqual(list_available_models(), [])


class OllamaChatResponseTests(TestCase):
    """Chat response parsing should tolerate null members in Ollama payloads."""

    @patch('core.services.ai.ollama_client.requests.post')
    def test_null_message_member_yields_empty_content(self, mock_post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {'message': None}
        mock_post.return_value = response

        self.assertEqual(_chat_with_ollama('test-model:1', []), '')


class OllamaModelResolutionTests(TestCase):
    """Model resolution should prioritize real-time availability."""

    @patch('core.services.ai.ollama_client.list_available_models', return_value=['qwen2.5:7b'])
    @override_settings(
        OLLAMA_DEFAULT_MODEL='configured-default:1',
        OLLAMA_MODEL_CANDIDATES=['configured-candidate:1'],
    )
    def test_resolve_model_name_prefers_detected_available_model_over_configured_defaults(
        self,
        _mock_list_available_models,
    ):
        self.assertEqual(resolve_model_name(), 'qwen2.5:7b')

    @patch('core.services.ai.ollama_client.list_available_models', return_value=[])
    @override_settings(
        OLLAMA_DEFAULT_MODEL='configured-default:1',
        OLLAMA_MODEL_CANDIDATES=['configured-candidate:1'],
    )
    def test_resolve_model_name_uses_configured_fallback_when_no_available_models(
        self,
        _mock_list_available_models,
    ):
        self.assertEqual(resolve_model_name(), 'configured-default:1')
