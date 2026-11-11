"""Full offline catalogue, tier/enchantment/quality filters and icon identity."""

import unittest

from samialbion.inventory_catalog import OfflineItemCatalog, item_category


class OfflineCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogue = OfflineItemCatalog()

    def test_catalogue_contains_all_saved_items(self):
        self.assertGreaterEqual(len(self.catalogue.items), 11000)
        self.assertEqual(len(self.catalogue.by_id), len(self.catalogue.items))

    def test_unnamed_technical_variants_are_not_displayed(self):
        self.assertNotIn("T4_ORE_LEVEL2", self.catalogue.by_id)
        self.assertTrue(all(item.name_fr or item.name_en for item in self.catalogue.items))
        named = self.catalogue.by_id["T8_ORE_LEVEL1@1"]
        self.assertIn("Minerai", named.name_fr)

    def test_equipment_and_raw_resource_categories(self):
        self.assertEqual(item_category("T4_MAIN_SWORD"), "Équipements")
        self.assertEqual(item_category("T8_ORE"), "Ressources brutes")
        self.assertEqual(item_category("T4_METALBAR"), "Ressources raffinées")
        self.assertEqual(item_category("T6_POTION_HEAL"), "Consommables")
        self.assertEqual(item_category("UNIQUE_ARMOR_VANITY_BARD"), "Cosmétiques")

    def test_tier_enchantment_metadata(self):
        ore = self.catalogue.by_id["T8_ORE_LEVEL1@1"]
        self.assertEqual((ore.tier, ore.enchantment), (8, 1))
        self.assertFalse(ore.has_qualities)
        sword = self.catalogue.by_id["T4_MAIN_SWORD"]
        self.assertEqual((sword.tier, sword.enchantment), (4, 0))
        self.assertTrue(sword.has_qualities)

    def test_filter_by_tier_enchantment_and_quality(self):
        results = self.catalogue.find("MAIN_SWORD", tier=4, enchantment=0, quality=5)
        self.assertTrue(results)
        self.assertTrue(all(item.tier == 4 and item.enchantment == 0 and item.has_qualities for item in results))
        self.assertFalse(self.catalogue.find("T8_ORE", quality=5))

    def test_search_accent_insensitive(self):
        result = self.catalogue.find("epée")
        self.assertTrue(result)

    def test_marketplace_has_exact_weapon_family_structure(self):
        self.assertEqual(self.catalogue.by_id["T4_2H_BOW"].market_path,
                         ("Armes", "Arc", "Arc"))
        self.assertEqual(self.catalogue.by_id["T4_2H_WARBOW"].market_path,
                         ("Armes", "Arc", "Arc de guerre"))
        self.assertEqual(self.catalogue.by_id["T7_2H_HAMMER_UNDEAD@3"].market_path,
                         ("Armes", "Marteau", "Martel-tombe"))

    def test_marketplace_filters_at_each_level(self):
        broad = self.catalogue.find(market_path=("Armes",))
        bows = self.catalogue.find(market_path=("Armes", "Arc"))
        warbows = self.catalogue.find(market_path=("Armes", "Arc", "Arc de guerre"))
        self.assertGreater(len(broad), len(bows))
        self.assertGreater(len(bows), len(warbows))
        self.assertTrue(all(item.market_path == ("Armes", "Arc", "Arc de guerre") for item in warbows))

    def test_refined_resources_use_detailed_marketplace_categories(self):
        self.assertEqual(self.catalogue.by_id["T8_ORE"].market_path,
                         ("Fabrication", "Ressources brutes", "Minerai"))
        self.assertEqual(self.catalogue.by_id["T4_METALBAR"].market_path,
                         ("Fabrication", "Ressources raffinées", "Lingot"))

    def test_vanity_items_stay_in_cosmetics(self):
        self.assertEqual(self.catalogue.by_id["UNIQUE_ARMOR_VANITY_BARD"].market_path[0],
                         "Cosmétique")


if __name__ == "__main__":
    unittest.main()
