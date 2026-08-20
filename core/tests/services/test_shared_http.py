"""HTTP helper behavior tests."""

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from core.models import Recipe
from core.views.shared.http import (
    MAX_SEARCH_QUERY_LENGTH,
    apply_recipe_search,
    get_client_ip,
)


class ClientIpResolutionTests(SimpleTestCase):
    """Client IP extraction should honor trusted proxy boundaries."""

    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(TRUSTED_PROXY_IPS=['127.0.0.1'])
    def test_trusted_proxy_uses_forwarded_for_first_hop(self):
        request = self.factory.get(
            '/',
            HTTP_X_FORWARDED_FOR='198.51.100.10, 127.0.0.1',
            REMOTE_ADDR='127.0.0.1',
        )
        self.assertEqual(get_client_ip(request), '198.51.100.10')

    @override_settings(TRUSTED_PROXY_IPS=['10.0.0.1'])
    def test_untrusted_proxy_ignores_forwarded_for(self):
        request = self.factory.get(
            '/',
            HTTP_X_FORWARDED_FOR='198.51.100.10, 127.0.0.1',
            REMOTE_ADDR='127.0.0.1',
        )
        self.assertEqual(get_client_ip(request), '127.0.0.1')

    @override_settings(TRUSTED_PROXY_IPS=['127.0.0.1'])
    def test_missing_remote_addr_falls_back_to_unknown(self):
        request = self.factory.get('/', HTTP_X_FORWARDED_FOR='198.51.100.10')
        request.META.pop('REMOTE_ADDR', None)
        self.assertEqual(get_client_ip(request), 'unknown')


class SearchQueryCapTests(TestCase):
    """Overlong search queries should be truncated before reaching the ORM."""

    def setUp(self):
        self.user_model = get_user_model()
        self.author = self.user_model.objects.create_user(
            username='search-cap-author',
            email='search-cap-author@example.com',
            first_name='Search',
            last_name='Cap',
            password='pwd-12345',
        )
        self.recipe = Recipe.objects.create(
            title='a' * MAX_SEARCH_QUERY_LENGTH,
            description='Query cap fixture.',
            cuisine='Home Style',
            flavor='savory',
            steps=['Cook'],
            cooking_time=20,
            difficulty='easy',
            nutrition={},
            author=self.author,
        )

    def test_search_query_is_truncated_to_max_length(self):
        queryset, _ = apply_recipe_search(
            Recipe.objects.all(),
            'a' * (MAX_SEARCH_QUERY_LENGTH + 50),
        )
        self.assertEqual([recipe.id for recipe in queryset], [self.recipe.id])
