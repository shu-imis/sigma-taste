"""High-level UI contracts for stable page structure and copy conventions."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Recipe, Review


class UIContractTests(TestCase):
    """Guard key rendering contracts without snapshot-heavy UI tests."""

    def setUp(self):
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(
            username='ui-contract-user',
            email='ui-contract-user@example.com',
            first_name='UI',
            last_name='Contract',
            password='pwd-12345',
        )
        self.recipe = Recipe.objects.create(
            title='contract recipe',
            description='Used to validate detail page title and structure.',
            cuisine='Home Style',
            flavor='savory',
            steps=['Step 1'],
            cooking_time=20,
            difficulty='easy',
            nutrition={},
            author=self.user,
        )

    def test_public_pages_keep_title_and_hero_group_contracts(self):
        cases = (
            ('web-home', 'DISCOVER · SIGMA TASTE', 'hero-group-discovery'),
            ('web-login', 'SIGN IN · SIGMA TASTE', 'hero-group-account'),
            ('web-register', 'CREATE ACCOUNT · SIGMA TASTE', 'hero-group-account'),
            ('web-boards', 'BOARDS · SIGMA TASTE', 'hero-group-studio'),
        )
        for route_name, expected_title, expected_hero_group in cases:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f'<title>{expected_title}</title>', html=True)
                self.assertContains(response, expected_hero_group)

    def test_authenticated_pages_keep_title_and_hero_group_contracts(self):
        self.client.force_login(self.user)
        cases = (
            ('web-recipe-create', 'RECIPE STUDIO · SIGMA TASTE', 'hero-group-studio'),
            ('web-ai-generate', 'AI RECIPE STUDIO · SIGMA TASTE', 'hero-group-studio'),
            ('web-profile', 'MY PROFILE · SIGMA TASTE', 'hero-group-studio'),
        )
        for route_name, expected_title, expected_hero_group in cases:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f'<title>{expected_title}</title>', html=True)
                self.assertContains(response, expected_hero_group)

    def test_login_protected_pages_redirect_anonymous_with_next_parameter(self):
        for route_name in ('web-profile', 'web-recipe-create', 'web-ai-generate'):
            with self.subTest(route=route_name):
                target = reverse(route_name)
                expected = f"{reverse('web-login')}?next={target}"
                response = self.client.get(target)
                self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_recipe_detail_uses_generic_tab_title_contract(self):
        response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<title>RECIPE DETAILS · SIGMA TASTE</title>', html=True)
        self.assertContains(response, 'hero-group-detail')

    def test_home_uses_card_tag_overflow(self):
        response = self.client.get(reverse('web-home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "core/js/card_tag_overflow.js")
        self.assertContains(response, 'data-card-tag-overflow')

    def test_boards_uses_non_article_list_markup(self):
        response = self.client.get(reverse('web-boards'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role="list"')
        self.assertContains(response, 'role="listitem"')
        self.assertNotContains(response, '<article class="card card-board">')

    def test_confirm_submit_script_is_loaded_only_on_recipe_detail(self):
        home_response = self.client.get(reverse('web-home'))
        self.assertEqual(home_response.status_code, 200)
        self.assertNotContains(home_response, "core/js/confirm_submit.js")

        detail_response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "core/js/confirm_submit.js")

    def test_form_progress_script_is_loaded_only_on_ai_related_forms(self):
        home_response = self.client.get(reverse('web-home'))
        self.assertEqual(home_response.status_code, 200)
        self.assertNotContains(home_response, "core/js/form_progress.js")

        self.client.force_login(self.user)
        create_response = self.client.get(reverse('web-recipe-create'))
        self.assertEqual(create_response.status_code, 200)
        self.assertContains(create_response, "core/js/form_progress.js")

        ai_response = self.client.get(reverse('web-ai-generate'))
        self.assertEqual(ai_response.status_code, 200)
        self.assertContains(ai_response, "core/js/form_progress.js")

    def test_ai_page_exposes_model_confirm_button(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('web-ai-generate'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="action" value="set_model"')
        self.assertContains(response, '>CONFIRM</button>')

    def test_ai_page_keeps_primary_submit_before_confirm_in_dom_order(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('web-ai-generate'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertLess(html.index('data-progress-submit'), html.index('name="action" value="set_model"'))

    def test_ai_progress_block_keeps_accessibility_contract(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('web-ai-generate'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-ai-progress-bar')
        self.assertContains(response, 'role="progressbar"')
        self.assertContains(response, 'aria-valuetext=')
        self.assertContains(response, 'data-ai-stage role="status" aria-live="polite"')
        self.assertContains(response, 'data-ai-progress-title')
        self.assertContains(response, '>Creating Your Recipe</span>', html=False)
        self.assertContains(response, '>Elapsed:</span>', html=False)

    def test_checkbox_line_copy_uses_shared_title_case_rule(self):
        self.client.force_login(self.user)

        profile_response = self.client.get(reverse('web-profile'))
        self.assertEqual(profile_response.status_code, 200)
        self.assertContains(profile_response, 'I Enjoy Spicy Dishes')
        self.assertContains(profile_response, 'I Enjoy Sweet Dishes')
        self.assertContains(profile_response, 'I Enjoy Sour Dishes')

        detail_response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, 'Post Anonymously')

    @patch('core.views.pages.ai.studio.list_available_models', return_value=['fixture-model'])
    @patch('core.views.pages.ai.studio.resolve_model_name', return_value='fixture-model')
    @patch(
        'core.views.pages.ai.studio.generate_recipe',
        return_value={
            'title': 'draft panel fixture',
            'description': 'Used to verify generated draft detail layout.',
            'cuisine': 'Home Style',
            'flavor': 'savory',
            'cooking_time': 20,
            'difficulty': 'easy',
            'ingredients': [{'name': 'Egg', 'quantity': '2', 'unit': 'pc', 'alternative': ''}],
            'steps': ['Cook gently.'],
            'nutrition': {},
        },
    )
    @patch('core.views.pages.ai.studio.issue_ai_draft', return_value=('fixture-draft-id', 'fixture-token'))
    def test_ai_generated_recipe_panel_uses_stacked_detail_cards(
        self,
        _mock_issue_ai_draft,
        _mock_generate_recipe,
        _mock_resolve_model_name,
        _mock_list_available_models,
    ):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('web-ai-generate'),
            {
                'model': 'fixture-model',
                'available_ingredients': 'egg',
                'cooking_time': 20,
                'flavor_preference': 'savory',
                'cuisine_preference': 'home style',
                'health_goal': 'balanced',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '>Draft Panel Fixture</h2>', html=False)
        self.assertContains(response, 'generated-recipe-detail-stack')
        self.assertNotContains(response, 'split generated-recipe-detail-grid')
        self.assertContains(response, 'recipe-info-card recipe-info-card-ingredients')
        self.assertContains(response, 'recipe-info-card recipe-info-card-steps')

    def test_base_layout_loads_only_global_shell_scripts(self):
        home_response = self.client.get(reverse('web-home'))
        self.assertEqual(home_response.status_code, 200)
        self.assertContains(home_response, "core/js/page_runtime.js")
        self.assertContains(home_response, "core/js/nav_shell.js")
        self.assertContains(home_response, "core/js/soft_nav.js")
        self.assertContains(home_response, 'data-global-script')

        login_response = self.client.get(reverse('web-login'))
        self.assertEqual(login_response.status_code, 200)
        self.assertContains(login_response, "core/js/page_runtime.js")
        self.assertContains(login_response, "core/js/nav_shell.js")
        self.assertContains(login_response, "core/js/soft_nav.js")
        self.assertContains(login_response, 'data-global-script')

        register_response = self.client.get(reverse('web-register'))
        self.assertEqual(register_response.status_code, 200)
        self.assertContains(register_response, "core/js/page_runtime.js")
        self.assertContains(register_response, "core/js/nav_shell.js")
        self.assertContains(register_response, "core/js/soft_nav.js")
        self.assertContains(register_response, 'data-global-script')

    def test_page_specific_scripts_are_tagged_for_soft_navigation_loading(self):
        home_response = self.client.get(reverse('web-home'))
        self.assertEqual(home_response.status_code, 200)
        self.assertContains(home_response, "core/js/card_tag_overflow.js")
        self.assertContains(home_response, 'data-page-script')

        detail_response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "core/js/confirm_submit.js")
        self.assertContains(detail_response, 'data-page-script')

        self.client.force_login(self.user)
        create_response = self.client.get(reverse('web-recipe-create'))
        self.assertEqual(create_response.status_code, 200)
        self.assertContains(create_response, "core/js/form_progress.js")
        self.assertContains(create_response, 'data-page-script')

        ai_response = self.client.get(reverse('web-ai-generate'))
        self.assertEqual(ai_response.status_code, 200)
        self.assertContains(ai_response, "core/js/form_progress.js")
        self.assertContains(ai_response, 'data-page-script')

    def test_display_copy_is_rendered_directly_in_dom_with_structured_casing(self):
        home_response = self.client.get(reverse('web-home'))
        self.assertEqual(home_response.status_code, 200)
        self.assertContains(home_response, '<h1>DISCOVER</h1>', html=True)
        self.assertContains(home_response, '>REFINE SEARCH</button>', html=False)
        self.assertContains(home_response, '>TRUSTED HOME RECIPES</span>', html=False)
        self.assertContains(home_response, '>START A RECIPE DRAFT</a>', html=False)
        self.assertContains(home_response, '>Contract Recipe</a>', html=False)
        self.assertContains(home_response, '>Home Style</span>', html=False)
        self.assertContains(home_response, '>20 min</span>', html=False)
        self.assertContains(home_response, '>Easy</span>', html=False)

        detail_response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, '<h1>Contract Recipe</h1>', html=True)
        self.assertContains(detail_response, '>Home Style</span>', html=False)
        self.assertContains(detail_response, '>20 min</span>', html=False)
        self.assertContains(detail_response, '>Easy</span>', html=False)
        self.assertContains(detail_response, '>1 views</span>', html=False)
        self.assertContains(detail_response, '>SAVORY</span>', html=False)
        self.assertContains(detail_response, '>Shared by ui-contract-user</span>', html=False)

    def test_profile_navigation_links_are_plain_server_routes(self):
        self.client.force_login(self.user)

        home_response = self.client.get(reverse('web-home'))
        self.assertEqual(home_response.status_code, 200)
        self.assertContains(home_response, 'href="/my-profile/"', html=False)

        profile_response = self.client.get(reverse('web-profile'))
        self.assertEqual(profile_response.status_code, 200)
        self.assertContains(profile_response, 'href="/my-profile/"', html=False)
        self.assertNotContains(profile_response, 'aria-current="page"', html=False)

    def test_profile_snapshot_uses_cjk_name_treatment_when_profile_name_is_chinese(self):
        cjk_user = self.user_model.objects.create_user(
            username='chen-meiyi',
            email='chen-meiyi@example.com',
            first_name='美怡',
            last_name='陈',
            password='pwd-12345',
        )
        self.client.force_login(cjk_user)
        response = self.client.get(reverse('web-profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'profile-summary-name is-cjk')
        self.assertContains(response, '陈美怡')

    def test_profile_snapshot_preserves_spacing_for_mixed_script_names(self):
        mixed_user = self.user_model.objects.create_user(
            username='meiyi-chen',
            email='meiyi-chen@example.com',
            first_name='Meiyi',
            last_name='陈',
            password='pwd-12345',
        )
        self.client.force_login(mixed_user)
        response = self.client.get(reverse('web-profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'profile-summary-name is-cjk-mixed')
        self.assertContains(response, 'Meiyi 陈')
        self.assertNotContains(response, '陈Meiyi')

    def test_navigation_avatar_uses_cjk_glyph_for_chinese_username(self):
        cjk_user = self.user_model.objects.create_user(
            username='陈同学_01',
            email='chen-avatar@example.com',
            first_name='同学',
            last_name='陈',
            password='pwd-12345',
        )
        self.client.force_login(cjk_user)
        response = self.client.get(reverse('web-home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'avatar-initial avatar-glyph is-cjk')
        self.assertContains(response, 'aria-label="User initial avatar">陈</span>', html=False)

    def test_review_avatar_uses_cjk_glyph_for_chinese_username(self):
        reviewer = self.user_model.objects.create_user(
            username='李味道-99',
            email='li-weidao@example.com',
            first_name='味道',
            last_name='李',
            password='pwd-12345',
        )
        Review.objects.create(recipe=self.recipe, user=reviewer, rating=5, content='Thoughtful review.')
        response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'review-avatar avatar-glyph is-cjk')
        self.assertContains(response, 'aria-hidden="true">李</span>', html=False)

    def test_sidebar_panels_use_shared_panel_contract(self):
        home_response = self.client.get(reverse('web-home'))
        self.assertEqual(home_response.status_code, 200)
        self.assertContains(home_response, 'data-panel-kind="link-list"')
        self.assertContains(home_response, 'data-panel-kind="action-list"')

        self.client.force_login(self.user)
        profile_response = self.client.get(reverse('web-profile'))
        self.assertEqual(profile_response.status_code, 200)
        self.assertContains(profile_response, 'data-panel-kind="summary-stack"')
        self.assertContains(profile_response, 'data-panel-kind="info-list"', count=1)

        create_response = self.client.get(reverse('web-recipe-create'))
        self.assertEqual(create_response.status_code, 200)
        self.assertContains(create_response, 'data-panel-kind="info-list"', count=2)

        ai_response = self.client.get(reverse('web-ai-generate'))
        self.assertEqual(ai_response.status_code, 200)
        self.assertContains(ai_response, 'data-panel-kind="info-list"', count=2)

    def test_primary_forms_and_feedback_panels_use_shared_panel_shell(self):
        login_response = self.client.get(reverse('web-login'))
        self.assertEqual(login_response.status_code, 200)
        self.assertContains(login_response, 'data-panel-shell', count=1)
        self.assertContains(login_response, 'data-auth-shell')

        register_response = self.client.get(reverse('web-register'))
        self.assertEqual(register_response.status_code, 200)
        self.assertContains(register_response, 'data-panel-shell', count=1)
        self.assertContains(register_response, 'data-auth-shell')

        detail_response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, 'data-panel-shell', count=1)

        self.client.force_login(self.user)

        profile_response = self.client.get(reverse('web-profile'))
        self.assertEqual(profile_response.status_code, 200)
        self.assertContains(profile_response, 'data-panel-shell', count=1)

        create_response = self.client.get(reverse('web-recipe-create'))
        self.assertEqual(create_response.status_code, 200)
        self.assertContains(create_response, 'data-panel-shell', count=1)

        ai_response = self.client.get(reverse('web-ai-generate'))
        self.assertEqual(ai_response.status_code, 200)
        self.assertContains(ai_response, 'data-panel-shell', count=1)

    def test_recipe_detail_uses_shared_feedback_blocks_for_empty_states(self):
        response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-feedback-kind="empty"', count=2)

    def test_local_empty_states_use_shared_section_empty_surface(self):
        detail_response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, 'class="recipe-empty section-empty"', count=1)
        self.assertContains(detail_response, 'class="empty section-empty"', count=2)

    def test_home_boards_and_detail_use_shared_section_heads_and_recipe_metrics(self):
        home_response = self.client.get(reverse('web-home'))
        self.assertEqual(home_response.status_code, 200)
        self.assertContains(home_response, 'data-section-head', count=1)
        self.assertContains(home_response, 'data-recipe-meta', count=1)
        self.assertContains(home_response, 'data-recipe-metrics', count=1)

        boards_response = self.client.get(reverse('web-boards'))
        self.assertEqual(boards_response.status_code, 200)
        self.assertContains(boards_response, 'data-section-head', count=1)
        self.assertContains(boards_response, 'data-recipe-metrics')

        detail_response = self.client.get(reverse('web-recipe-detail', args=[self.recipe.id]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, 'data-section-head', count=1)

    def test_shared_partials_back_hero_empty_state_editor_and_auth_shells(self):
        home_response = self.client.get(reverse('web-home'), {'q': 'no-shared-empty-state-match'})
        self.assertEqual(home_response.status_code, 200)
        self.assertContains(home_response, 'data-hero-support')
        self.assertContains(home_response, 'data-empty-state')

        boards_response = self.client.get(reverse('web-boards'))
        self.assertEqual(boards_response.status_code, 200)
        self.assertContains(boards_response, 'data-hero-support')

        login_response = self.client.get(reverse('web-login'))
        self.assertEqual(login_response.status_code, 200)
        self.assertContains(login_response, 'data-auth-shell')

        register_response = self.client.get(reverse('web-register'))
        self.assertEqual(register_response.status_code, 200)
        self.assertContains(register_response, 'data-auth-shell')

        self.client.force_login(self.user)
        profile_response = self.client.get(reverse('web-profile'))
        self.assertEqual(profile_response.status_code, 200)
        self.assertContains(profile_response, 'data-editor-section-head', count=2)

        create_response = self.client.get(reverse('web-recipe-create'))
        self.assertEqual(create_response.status_code, 200)
        self.assertContains(create_response, 'data-editor-section-head', count=3)

        ai_response = self.client.get(reverse('web-ai-generate'))
        self.assertEqual(ai_response.status_code, 200)
        self.assertContains(ai_response, 'data-editor-section-head', count=1)

    def test_base_layout_loads_core_stylesheets(self):
        response = self.client.get(reverse('web-home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "core/css/tokens.css")
        self.assertContains(response, "core/css/utilities.css")
