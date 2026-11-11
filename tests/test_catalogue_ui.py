"""GUI smoke tests use the real offline data and bundled icons."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QApplication
    from samialbion.catalogue_page import CataloguePage, NeutralIconDelegate
    from samialbion.ui_calculator import ASSETS
except ImportError:
    QApplication = None


@unittest.skipUnless(QApplication is not None, "PySide6 not installed")
class CatalogueUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.app.setStyleSheet((ASSETS / "tavern.qss").read_text(encoding="utf-8"))

    def setUp(self):
        self.page = CataloguePage()
        self.page.resize(900, 650)
        self.page.show()
        self.app.processEvents()

    def tearDown(self):
        self.page.close()

    def test_all_items_visible_and_offline_icon_loads(self):
        self.assertGreaterEqual(self.page.model.rowCount(), 11000)
        self.assertGreater(self.page.icons.count, 0)
        self.assertTrue(self.page.icons.has_icon("T4_MAIN_SWORD"))

    def test_technical_identifiers_and_footer_note_are_hidden(self):
        self.page._select_market_path(("Fabrication", "Ressources brutes", "Minerai"))
        self.page.tier.setCurrentIndex(4)
        self.page._refresh()
        names = [self.page.model.data(self.page.model.index(row, 0))
                 for row in range(self.page.model.rowCount())]
        self.assertNotIn("T4_ORE_LEVEL2", names)
        self.assertFalse(any(name.startswith("T4_ORE_LEVEL") for name in names))
        self.assertNotIn("ID :", self.page.detail_data.text())
        self.assertFalse(hasattr(self.page, "image_info"))
        self.assertNotIn("T4_ORE", str(self.page.model.data(
            self.page.model.index(0, 0), Qt.ItemDataRole.ToolTipRole)))

    def test_search_and_quality_filter(self):
        self.page.search.setText("T4_MAIN_SWORD")
        self.page.quality.setCurrentIndex(5)
        self.page._refresh()
        self.assertGreater(self.page.model.rowCount(), 0)
        self.assertTrue(all(item.has_qualities for item in self.page.model.items))

    def test_nested_market_category_filters(self):
        self.page._select_market_path(("Armes", "Arc", "Arc de guerre"))
        self.assertGreater(self.page.model.rowCount(), 0)
        self.assertTrue(all(x.market_path == ("Armes", "Arc", "Arc de guerre")
                            for x in self.page.model.items))
        self.assertIn("Arc de guerre", self.page.category_button.text())

    def test_selected_icon_is_normal_pixmap_without_qt_tint(self):
        self.page.search.setText("T4_MAIN_SWORD")
        self.page._refresh()
        decoration = self.page.model.data(self.page.model.index(0, 0),
                                          Qt.ItemDataRole.DecorationRole)
        self.assertIsInstance(decoration, QPixmap)
        self.assertIsInstance(self.page.table.itemDelegateForColumn(0), NeutralIconDelegate)

    def test_selected_row_does_not_recolour_carrot_or_other_icons(self):
        for identifier in ("T1_CARROT", "T4_MAIN_SWORD"):
            with self.subTest(item=identifier):
                self.page.search.setText(identifier)
                self.page._refresh()
                self.app.processEvents()
                self.assertGreater(self.page.model.rowCount(), 0)
                cell = self.page.table.visualRect(self.page.model.index(0, 0))
                icon_x = cell.left() + 9
                icon_y = cell.top() + (cell.height() - 43) // 2
                selected = self.page.table.viewport().grab().toImage()
                self.page.table.clearSelection()
                self.app.processEvents()
                unselected = self.page.table.viewport().grab().toImage()
                for y in range(43):
                    for x in range(43):
                        self.assertEqual(
                            selected.pixelColor(icon_x + x, icon_y + y),
                            unselected.pixelColor(icon_x + x, icon_y + y),
                            f"Tint detected at {x},{y} for {identifier}",
                        )

    def test_market_menu_has_three_levels(self):
        menu = self.page.category_button.menu()
        weapons = next(x.menu() for x in menu.actions() if x.text() == "Armes")
        bows = next(x.menu() for x in weapons.actions() if x.text() == "Arc")
        self.assertIsNotNone(bows)
        self.page._open_leaf_menu(bows, "Armes", "Arc", ("Arc", "Arc de guerre"))
        self.assertIn("Arc de guerre", [x.text() for x in bows.actions()])
        next(x for x in bows.actions() if x.text() == "Arc de guerre").trigger()
        self.assertEqual(self.page.market_path, ("Armes", "Arc", "Arc de guerre"))


if __name__ == "__main__":
    unittest.main()
