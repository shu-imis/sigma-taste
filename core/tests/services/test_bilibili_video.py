"""Tests for Bilibili tutorial video parsing helpers."""

from types import SimpleNamespace

from django.test import SimpleTestCase

from core.services.video import get_recipe_tutorial_video_info, parse_bilibili_video_url


class BilibiliVideoParsingTests(SimpleTestCase):
    """Bilibili parser should normalize supported URL shapes safely."""

    def test_parse_standard_bvid_url(self):
        parsed = parse_bilibili_video_url('https://www.bilibili.com/video/BV1xx411c7mD?p=2')
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['provider'], 'bilibili')
        self.assertEqual(parsed['bvid'], 'BV1xx411c7mD')
        self.assertEqual(parsed['page'], 2)
        self.assertEqual(parsed['embed_url'], 'https://player.bilibili.com/player.html?bvid=BV1xx411c7mD&page=2')

    def test_parse_player_url_with_bvid(self):
        parsed = parse_bilibili_video_url('https://player.bilibili.com/player.html?bvid=BV1ab411c7mD&page=3')
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['bvid'], 'BV1ab411c7mD')
        self.assertEqual(parsed['page'], 3)
        self.assertEqual(parsed['source_url'], 'https://www.bilibili.com/video/BV1ab411c7mD?p=3')

    def test_parse_legacy_av_url(self):
        parsed = parse_bilibili_video_url('https://www.bilibili.com/video/av12345678?p=1')
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['aid'], '12345678')
        self.assertEqual(parsed['page'], 1)
        self.assertEqual(parsed['embed_url'], 'https://player.bilibili.com/player.html?aid=12345678&page=1')

    def test_parse_rejects_short_link_host(self):
        self.assertIsNone(parse_bilibili_video_url('https://b23.tv/abcd'))


class RecipeTutorialVideoInfoTests(SimpleTestCase):
    """Recipe detail helper should return embeddable or fallback link context."""

    def test_returns_embeddable_info_for_bilibili_url(self):
        recipe = SimpleNamespace(tutorial_video_url='https://m.bilibili.com/video/BV1xx411c7mD')
        info = get_recipe_tutorial_video_info(recipe)

        self.assertIsNotNone(info)
        self.assertEqual(info['provider'], 'bilibili')
        self.assertTrue(info['is_embeddable'])
        self.assertIn('player.bilibili.com/player.html', info['embed_url'])

    def test_returns_external_info_for_non_bilibili_url(self):
        recipe = SimpleNamespace(tutorial_video_url='https://example.com/tutorial')
        info = get_recipe_tutorial_video_info(recipe)

        self.assertIsNotNone(info)
        self.assertEqual(info['provider'], 'external')
        self.assertFalse(info['is_embeddable'])
        self.assertEqual(info['source_url'], 'https://example.com/tutorial')

    def test_returns_none_when_missing_url(self):
        recipe = SimpleNamespace(tutorial_video_url='')
        self.assertIsNone(get_recipe_tutorial_video_info(recipe))
