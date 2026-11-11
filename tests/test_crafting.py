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

    def test_requested_units_round_up_for_multi_output_recipe(self):
        recipe = self.recipes.by_id["T2_POTION_HEAL"]
        result = calculate_profit(recipe, {"T2_AGARIC": 100}, 300,
                                  target_units=31)
        self.assertEqual(result.batches, 7)
        self.assertEqual(result.produced, 35)
        self.assertEqual(result.upfront_cost, 5600)
        self.assertEqual(result.revenue, 10500)

    def test_tax_craft_fee_and_resource_return_are_applied(self):
        recipe = self.recipes.by_id["T4_MAIN_SWORD"]
        result = calculate_profit(
            recipe, {"T4_METALBAR": 100, "T4_LEATHER": 200}, 5000,
            target_units=2, market_tax_enabled=True, artisan_fee_per_batch=100,
            return_percent=20,
        )
        self.assertEqual(result.upfront_cost, 6400)
        self.assertEqual(result.recovered_value, 1280)
        self.assertEqual(result.cost, 5120)
        self.assertEqual(result.market_fee, 650)
        self.assertEqual(result.artisan_fee, 200)
        self.assertEqual(result.profit, 4030)

    def test_unchecked_tax_does_not_reduce_profit(self):
        recipe = self.recipes.by_id["T4_MAIN_SWORD"]
        result = calculate_profit(recipe, {"T4_METALBAR": 100}, 5000,
                                  market_tax_enabled=False)
        self.assertEqual(result.market_fee, 0)


if __name__ == "__main__":
    unittest.main()
