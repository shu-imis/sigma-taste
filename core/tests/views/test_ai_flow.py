"""AI generation and publish flow tests."""

from unittest.mock import Mock, patch

import requests
from django.core.cache import cache
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Recipe, UserPreference
from core.services.ai import OllamaError, list_available_models, resolve_model_name
from core.services.ai.ollama_client import (
    MODEL_LIST_CACHE_KEY,
    SELECTED_MODEL_SESSION_KEY,
    _chat_with_ollama,
)
from core.tests.utils import force_session_key, make_ai_draft_bundle, make_user
from core.views.pages.ai import studio as ai_actions
from core.views.shared.ai import ai_draft_cache_key
from core.views.shared.idempotency import idempotency_ttl_seconds, inflight_marker


def _ai_payload(**overrides):
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


def _generated_recipe(title, description):
    return {
        'title': title,
        'description': description,
        'cuisine': 'Home Style',
        'flavor': 'savory',
        'cooking_time': 20,
        'difficulty': 'easy',
        'ingredients': [{'name': 'egg', 'quantity': '2', 'unit': 'pc', 'alternative': ''}],
        'steps': ['Cook and serve'],
        'nutrition': {},
    }


class AIDraftSecurityTests(TestCase):
    """Security and integrity checks for AI draft publishing."""

    def setUp(self):
        cache.clear()
        self.user = make_user(
            username='ai-cooker',
            email='ai-cooker@example.com',
            first_name='Cook',
            last_name='User',
        )
        self.client.force_login(self.user)
        self.session_key = force_session_key(self.client)

    def _build_valid_draft_bundle(self, *, session_key=None, issued_for_user_id=None):
        return make_ai_draft_bundle(
            session_key=session_key or self.session_key,
            user_id=self.user.id if issued_for_user_id is None else issued_for_user_id,
            generated_recipe={
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
            source_payload={
                'available_ingredients': ['tofu', 'pepper'],
                'cooking_time': 15,
                'flavor_preference': 'savory',
                'cuisine_preference': 'home style',
                'health_goal': 'balanced',
            },
        )

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
        self.assertIsNone(cache.get(ai_draft_cache_key(draft_id)))

    def test_publish_generated_rejects_token_issued_for_different_user(self):
        other_user = make_user(
            username='ai-other-cooker',
            email='ai-other-cooker@example.com',
            first_name='Other',
            last_name='Cook',
        )
        self.client.force_login(other_user)
        other_session_key = force_session_key(self.client)

        draft_id, draft_token = self._build_valid_draft_bundle(
            session_key=other_session_key,
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
        self.assertContains(response, 'Save to recipe box')

    def test_publish_generated_rejects_draft_consumed_by_recipe_studio(self):
        draft_id, draft_token = self._build_valid_draft_bundle()
        create_response = self.client.post(
            reverse('web-recipe-create'),
            {
                'title': 'Studio Signed Stir-Fry',
                'description': 'Created from the same AI draft.',
                'cuisine': 'Home Style',
                'flavor': 'savory',
                'cooking_time': 15,
                'difficulty': 'easy',
                'steps_text': '1. Prep ingredients\n2. Stir-fry and serve',
                'ingredients_text': 'Tofu,200,g,\nPepper,1,pc,',
                'source_draft_id': draft_id,
                'source_draft_token': draft_token,
            },
        )
        self.assertEqual(create_response.status_code, 302)

        publish_response = self.client.post(
            reverse('web-ai-generate'),
            {
                'action': 'publish_generated',
                'draft_id': draft_id,
                'draft_token': draft_token,
            },
        )
        self.assertEqual(publish_response.status_code, 200)
        self.assertContains(publish_response, 'no longer available')
        self.assertEqual(Recipe.objects.count(), 1)

    @patch('core.views.shared.ai.issue_ai_draft', return_value=('reissued-draft-id', 'reissued-token'))
    @patch('core.views.pages.ai.studio.create_recipe_with_ingredients', side_effect=DatabaseError('db write failure'))
    def test_publish_generated_reissues_draft_when_save_fails(self, _mock_create_recipe, mock_issue_ai_draft):
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
        self.assertContains(response, 'We could not save that recipe right now.')
        self.assertContains(response, 'Signed Stir-Fry')
        self.assertContains(response, 'value="reissued-token"')
        self.assertContains(response, 'value="reissued-draft-id"')
        self.assertEqual(Recipe.objects.count(), 0)
        mock_issue_ai_draft.assert_called_once()
        reissued = mock_issue_ai_draft.call_args.kwargs
        self.assertEqual(reissued['generated_recipe']['title'], 'Signed Stir-Fry')
        self.assertEqual(reissued['source_payload']['model'], 'test-model:1')
        self.assertEqual(reissued['model'], 'test-model:1')

    @patch('core.views.shared.ai.issue_ai_draft')
    @patch('core.views.pages.ai.studio.create_recipe_with_ingredients', side_effect=TypeError('programming error'))
    def test_publish_generated_propagates_unexpected_errors(self, _mock_create_recipe, mock_issue_ai_draft):
        draft_id, draft_token = self._build_valid_draft_bundle()

        with self.assertRaises(TypeError):
            self.client.post(
                reverse('web-ai-generate'),
                {
                    'action': 'publish_generated',
                    'draft_id': draft_id,
                    'draft_token': draft_token,
                },
            )
        mock_issue_ai_draft.assert_not_called()


class AIAnonymousAccessTests(TestCase):
    """Anonymous users should not be able to use AI preview actions."""

    @patch('core.views.pages.ai.studio.generate_recipe')
    def test_anonymous_user_cannot_post_generate_preview(self, mock_generate):
        response = self.client.post(reverse('web-ai-generate'), _ai_payload())
        expected = f"{reverse('web-login')}?next={reverse('web-ai-generate')}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)
        mock_generate.assert_not_called()


class AIGenerateErrorMessageTests(TestCase):
    """User-facing AI errors should not expose internal exception details."""

    def setUp(self):
        cache.clear()
        self.user = make_user(
            username='ai-errors-user',
            email='ai-errors-user@example.com',
            first_name='Ai',
            last_name='Errors',
        )
        self.client.force_login(self.user)

    @patch('core.views.pages.ai.studio.resolve_model_name', side_effect=OllamaError('connection refused'))
    def test_model_resolution_error_is_sanitized(self, _mock_resolve_model_name):
        response = self.client.post(reverse('web-ai-generate'), _ai_payload())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose an available local model to continue.')
        self.assertNotContains(response, 'connection refused')

    @patch('core.views.pages.ai.studio.resolve_model_name', return_value='test-model:1')
    @patch('core.views.pages.ai.studio.generate_recipe', side_effect=OllamaError('socket timeout'))
    def test_generation_error_is_sanitized(self, _mock_generate_recipe, _mock_resolve_model_name):
        response = self.client.post(reverse('web-ai-generate'), _ai_payload())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'AI recipe generation is unavailable right now. Please try again shortly.')
        self.assertNotContains(response, 'socket timeout')


class AIGenerateDefaultModelSelectionTests(TestCase):
    """AI page model input should follow detected local model availability."""

    def setUp(self):
        cache.clear()
        self.user = make_user(
            username='ai-default-model-user',
            email='ai-default-model-user@example.com',
            first_name='Ai',
            last_name='DefaultModel',
        )
        self.client.force_login(self.user)

    def _payload(self, **overrides):
        overrides.setdefault('model', 'qwen2.5:7b')
        return _ai_payload(**overrides)

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
        mock_generate_recipe.return_value = _generated_recipe(
            'Allergy Aware Recipe',
            'Generated with allergy context.',
        )

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
        self.assertContains(response, 'No local model is ready yet. Enable one in Ollama, then refresh this page.')

    @patch('core.views.pages.ai.studio.list_available_models', return_value=['qwen2.5:7b', 'llama3.1:8b'])
    def test_ai_page_prefills_session_selected_model_when_still_available(self, _mock_list_available_models):
        session = self.client.session
        session[SELECTED_MODEL_SESSION_KEY] = 'llama3.1:8b'
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
        mock_generate_recipe.return_value = _generated_recipe(
            'Cached Draft Recipe',
            'Generated once and reused within idempotency window.',
        )

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
        cache.set(inflight_key, inflight_marker(), timeout=idempotency_ttl_seconds('IDEMPOTENCY_AI_GENERATE_WINDOW_SECONDS'))

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
        mock_generate_recipe.return_value = _generated_recipe(
            'Parsed Ingredient Recipe',
            'Generated with normalized ingredient list.',
        )

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
        mock_generate_recipe.return_value = _generated_recipe(
            'Bullet List Ingredient Recipe',
            'Generated from bulleted ingredient input.',
        )

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

    @patch('core.views.pages.ai.studio.list_available_models', return_value=['qwen2.5:7b'])
    @patch('core.views.pages.ai.studio.generate_recipe')
    def test_generate_rejects_model_not_in_available_list(self, mock_generate_recipe, _mock_list_available_models):
        response = self.client.post(reverse('web-ai-generate'), self._payload(model='unlisted-model:1'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose an available local model to continue.')
        mock_generate_recipe.assert_not_called()

    @patch('core.views.pages.ai.studio.list_available_models', return_value=['qwen2.5:7b', 'llama3.1:8b'])
    def test_set_model_action_confirms_valid_model_without_generation(
        self,
        _mock_list_available_models,
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
        self.assertContains(response, 'Your model is ready when you are.')
        self.assertContains(response, 'option value="llama3.1:8b" selected', html=False)
        self.assertContains(response, 'egg, tomato')
        self.assertContains(response, 'name="cooking_time" value="30"')
        self.assertContains(response, 'name="flavor_preference" value="savory"')
        self.assertEqual(self.client.session.get(SELECTED_MODEL_SESSION_KEY), 'llama3.1:8b')

    @patch('core.views.pages.ai.studio.list_available_models')
    def test_set_model_action_refreshes_model_list_before_validation(
        self,
        mock_list_available_models,
    ):
        mock_list_available_models.side_effect = [
            ['qwen2.5:7b'],
            ['qwen2.5:7b', 'llama3.1:8b'],
        ]
        response = self.client.post(
            reverse('web-ai-generate'),
            {'action': 'set_model', 'model': 'llama3.1:8b'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your model is ready when you are.')
        self.assertEqual(self.client.session.get(SELECTED_MODEL_SESSION_KEY), 'llama3.1:8b')

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

    @override_settings(RATE_LIMITS={'ai_set_model': {'limit': 1, 'window': 60}})
    @patch('core.views.pages.ai.studio.list_available_models', return_value=['qwen2.5:7b'])
    def test_set_model_action_is_rate_limited(self, _mock_list_available_models):
        first = self.client.post(
            reverse('web-ai-generate'),
            {'action': 'set_model', 'model': 'qwen2.5:7b'},
        )
        self.assertEqual(first.status_code, 200)
        self.assertContains(first, 'Your model is ready when you are.')

        second = self.client.post(
            reverse('web-ai-generate'),
            {'action': 'set_model', 'model': 'qwen2.5:7b'},
        )
        self.assertEqual(second.status_code, 200)
        self.assertContains(second, 'Too many model updates. Please give it a moment and try again.')


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
        mock_cache_set.assert_called_once_with(MODEL_LIST_CACHE_KEY, [], timeout=5)

    @patch('core.services.ai.ollama_client.requests.get')
    def test_model_list_tolerates_null_models_member(self, mock_get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {'models': None}
        mock_get.return_value = response

        self.assertEqual(list_available_models(), [])

    @patch('core.services.ai.ollama_client.requests.get')
    def test_model_list_tolerates_non_dict_payload(self, mock_get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = ['not', 'a', 'dict']
        mock_get.return_value = response

        self.assertEqual(list_available_models(), [])

    @patch('core.services.ai.ollama_client.requests.get')
    def test_model_list_skips_non_dict_model_entries(self, mock_get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {'models': ['oops', {'model': 'qwen2.5:7b'}, None]}
        mock_get.return_value = response

        self.assertEqual(list_available_models(), ['qwen2.5:7b'])


class OllamaMalformedPayloadPageTests(TestCase):
    """Malformed Ollama payloads should degrade the AI page, never 500 it."""

    def setUp(self):
        cache.clear()
        self.user = make_user(
            username='jane-doe',
            email='jane.doe@example.com',
            first_name='Jane',
            last_name='Doe',
        )
        self.client.force_login(self.user)

    @patch('core.services.ai.ollama_client.requests.get')
    def test_ai_page_degrades_when_tags_payload_is_a_json_array(self, mock_get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = ['unexpected-array']
        mock_get.return_value = response

        page = self.client.get(reverse('web-ai-generate'))

        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'No local model is ready yet.')


class OllamaChatResponseTests(TestCase):
    """Chat response parsing should tolerate null members in Ollama payloads."""

    @patch('core.services.ai.ollama_client.requests.post')
    def test_null_message_member_yields_empty_content(self, mock_post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {'message': None}
        mock_post.return_value = response

        self.assertEqual(_chat_with_ollama('test-model:1', []), '')

    @patch('core.services.ai.ollama_client.requests.post')
    def test_non_dict_chat_payload_raises_ollama_error(self, mock_post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = ['unexpected-array']
        mock_post.return_value = response

        with self.assertRaises(OllamaError):
            _chat_with_ollama('test-model:1', [])

    @patch('core.services.ai.ollama_client.requests.post')
    def test_string_message_member_raises_ollama_error(self, mock_post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {'message': 'a string'}
        mock_post.return_value = response

        with self.assertRaises(OllamaError):
            _chat_with_ollama('test-model:1', [])

    @patch('core.services.ai.ollama_client.requests.post')
    def test_non_string_content_member_raises_ollama_error(self, mock_post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {'message': {'content': ['not', 'text']}}
        mock_post.return_value = response

        with self.assertRaises(OllamaError):
            _chat_with_ollama('test-model:1', [])


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
