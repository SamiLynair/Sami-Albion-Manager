"""Craft recipe coverage and silver calculations."""

import unittest

from samialbion.crafting import CraftingRecipes, calculate_profit
from samialbion.inventory_catalog import OfflineItemCatalog


class CraftingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipes = CraftingRecipes()
        cls.catalog = OfflineItemCatalog()

    def test_real_weapon_recipe_and_enchantments(self):
        recipe = self.recipes.by_id["T4_MAIN_SWORD"]
        self.assertEqual(recipe.output_amount, 1)
        self.assertEqual(dict(recipe.materials), {"T4_METALBAR": 16, "T4_LEATHER": 8})
        enchanted = self.recipes.by_id["T4_MAIN_SWORD@1"]
        self.assertEqual(dict(enchanted.materials)["T4_METALBAR_LEVEL1@1"], 16)

    def test_potion_outputs_five(self):
        recipe = self.recipes.by_id["T2_POTION_HEAL"]
        self.assertEqual(recipe.output_amount, 5)
        self.assertEqual(recipe.materials, (("T2_AGARIC", 8),))

    def test_profit_uses_quantities_and_output(self):
        recipe = self.recipes.by_id["T4_MAIN_SWORD"]
        result = calculate_profit(recipe, {"T4_METALBAR": 100, "T4_LEATHER": 200}, 5000, 2)
        self.assertEqual(result.cost, 6400)
        self.assertEqual(result.revenue, 10000)
        self.assertEqual(result.profit, 3600)
        self.assertAlmostEqual(result.roi_percent, 56.25)
        self.assertAlmostEqual(result.margin_percent, 36.0)

    def test_recipe_material_names_exist_in_catalog(self):
        for recipe in self.recipes.by_id.values():
            self.assertIn(recipe.item_id, self.catalog.by_id)
            self.assertTrue(all(item_id in self.catalog.by_id for item_id, _ in recipe.materials))

    def test_missing_prices_are_zero_without_fake_profit(self):
        result = calculate_profit(self.recipes.by_id["T2_POTION_HEAL"], {}, 0)
        self.assertEqual(result.profit, 0)
        self.assertIsNone(result.roi_percent)


if __name__ == "__main__":
    unittest.main()
