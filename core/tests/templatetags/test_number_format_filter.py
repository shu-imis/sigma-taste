"""Tests for compact numeric formatting in templates."""

from django.test import SimpleTestCase

from core.templatetags.number_format import compact_number


class CompactNumberFilterTests(SimpleTestCase):
    """Compact formatting should stay predictable across key magnitudes."""

    def test_returns_original_value_for_non_numeric_input(self):
        self.assertEqual(compact_number("not-a-number"), "not-a-number")

    def test_keeps_plain_numbers_below_one_thousand(self):
        self.assertEqual(compact_number(987), "987")
        self.assertEqual(compact_number("12.3400"), "12.34")

    def test_formats_thousands_with_k_suffix(self):
        self.assertEqual(compact_number(1000), "1K")
        self.assertEqual(compact_number(1540), "1.5K")
        self.assertEqual(compact_number(12500), "12.5K")

    def test_formats_millions_and_billions(self):
        self.assertEqual(compact_number(1_000_000), "1M")
        self.assertEqual(compact_number(1_200_000_000), "1.2B")

    def test_rolls_up_at_unit_boundary_after_rounding(self):
        self.assertEqual(compact_number(999_950), "1M")

    def test_preserves_negative_sign(self):
        self.assertEqual(compact_number(-2300), "-2.3K")
