"""Tests for recipe form input parsing helpers."""

from django.test import SimpleTestCase

from core.models import Ingredient
from core.views.shared.recipe import parse_ingredients, parse_steps


class ParseStepsTests(SimpleTestCase):
    """Step lines should drop common list markers before storage."""

    def test_dash_before_number_prefix_is_removed(self):
        self.assertEqual(parse_steps('- 1. Mix ingredients'), ['Mix ingredients'])

    def test_numbered_and_plain_lines_are_cleaned(self):
        self.assertEqual(
            parse_steps('1. Boil water\n- Drain noodles\nServe hot'),
            ['Boil water', 'Drain noodles', 'Serve hot'],
        )

    def test_leading_quantities_without_list_markers_are_preserved(self):
        self.assertEqual(
            parse_steps('300g flour, sifted\n2 eggs, beaten'),
            ['300g flour, sifted', '2 eggs, beaten'],
        )

    def test_decimal_quantity_is_not_treated_as_list_numbering(self):
        self.assertEqual(parse_steps('1.5kg potatoes, boiled'), ['1.5kg potatoes, boiled'])

    def test_parenthesized_list_numbering_is_removed(self):
        self.assertEqual(parse_steps('2) Fold in cheese'), ['Fold in cheese'])


class ParseIngredientsTests(SimpleTestCase):
    """Parsed ingredient rows should respect the Ingredient model limits."""

    def test_csv_like_rows_are_parsed(self):
        self.assertEqual(
            parse_ingredients('Tofu,200,g,\nPepper,1,pc,chili'),
            [
                {'name': 'Tofu', 'quantity': '200', 'unit': 'g', 'alternative': ''},
                {'name': 'Pepper', 'quantity': '1', 'unit': 'pc', 'alternative': 'chili'},
            ],
        )

    def test_fields_are_clamped_to_model_max_lengths(self):
        rows = parse_ingredients(f"{'n' * 150},{'q' * 80},{'u' * 40},{'a' * 150}")
        row = rows[0]
        self.assertEqual(len(row['name']), Ingredient._meta.get_field('name').max_length)
        self.assertEqual(len(row['quantity']), Ingredient._meta.get_field('quantity').max_length)
        self.assertEqual(len(row['unit']), Ingredient._meta.get_field('unit').max_length)
        self.assertEqual(len(row['alternative']), Ingredient._meta.get_field('alternative').max_length)
