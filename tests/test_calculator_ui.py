"""Minimal smoke tests for the collapsible calculator in headless Qt."""

import os
import unittest

from samialbion import __version__

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLabel
    from samialbion.ui_calculator import ASSETS, WorkshopWindow
except ImportError:
    QApplication = None


@unittest.skipUnless(QApplication is not None, "PySide6 not installed")
class CalculatorUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.app.setStyleSheet((ASSETS / "tavern.qss").read_text(encoding="utf-8"))

    def setUp(self):
        self.window = WorkshopWindow()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()

    def test_drawer_defaults_to_closed_and_opens_only_on_demand(self):
        self.assertFalse(self.window.expanded)
        self.assertFalse(self.window.drawer.isVisible())
        self.assertIn("▾", self.window.drawer_button.text())
        self.assertLess(self.window.drawer.sizeHint().height(), 290)
        self.window.toggle_calculator(animate=False)
        self.assertTrue(self.window.expanded)
        self.assertTrue(self.window.drawer.isVisible())
        self.window.toggle_calculator(animate=False)
        self.assertFalse(self.window.expanded)
        self.assertFalse(self.window.drawer.isVisible())

    def test_buttons_calculate_and_keep_value_when_closed(self):
        self.window.toggle_calculator(animate=False)
        for symbol in ("1", "2", "+", "3", "="):
            self.window.drawer.key_buttons[symbol].click()
        self.assertEqual(self.window.drawer.value.text(), "15")
        self.window.toggle_calculator(animate=False)
        self.window.toggle_calculator(animate=False)
        self.assertEqual(self.window.drawer.value.text(), "15")

    def test_author_and_version_in_sidebar(self):
        self.assertEqual(self.window.author_label.text(), "Made by Sami")
        self.assertEqual(self.window.version_label.text(), f"v{__version__}")
        labels = [label.text() for label in self.window.findChildren(QLabel)]
        self.assertNotIn("FAN-MADE", labels)
        self.assertTrue(self.window.settings_button.isEnabled())

    def test_crafting_is_home_and_first_navigation_item(self):
        self.assertEqual(self.window.pages.currentWidget(), self.window.crafting_page)
        self.assertEqual(self.window.crafting_button.property("active"), "true")
        self.assertEqual(self.window.catalogue_button.property("active"), "false")
        sidebar = self.window.crafting_button.parentWidget().layout()
        self.assertLess(sidebar.indexOf(self.window.crafting_button),
                        sidebar.indexOf(self.window.catalogue_button))
        self.assertEqual(self.window.banner.height(), 145)
        self.window.catalogue_button.click()
        self.assertEqual(self.window.pages.currentWidget(), self.window.catalogue_page)
        self.window.crafting_button.click()
        self.assertEqual(self.window.pages.currentWidget(), self.window.crafting_page)

    def test_github_updates_button_is_available(self):
        self.assertEqual(self.window.updates_button.text(), "↻   Mises à jour")
        self.assertIsNotNone(self.window.update_controller)
        self.assertEqual(self.window.pages.currentWidget(), self.window.crafting_page)
        self.window.settings_button.click()
        self.assertEqual(self.window.pages.currentWidget(), self.window.settings_page)
        self.assertTrue(self.window.updates_button.isVisible())
        self.window.catalogue_button.click()
        self.assertEqual(self.window.pages.currentWidget(), self.window.catalogue_page)

    def test_banner_keeps_catalogue_dimensions_on_every_page(self):
        # All screens (including future ones) share the same banner widget.
        expected_height = 145
        self.assertEqual(self.window.banner.height(), expected_height)
        self.window.catalogue_button.click()
        self.assertEqual(self.window.banner.height(), expected_height)
        self.window.crafting_button.click()
        self.assertEqual(self.window.banner.height(), expected_height)
        self.window.settings_button.click()
        self.assertEqual(self.window.banner.height(), expected_height)
        self.assertEqual(self.window.banner.minimumHeight(), expected_height)
        self.assertEqual(self.window.banner.maximumHeight(), expected_height)

    def test_clean_window_title_and_artisan_branding(self):
        self.assertEqual(self.window.windowTitle(), f"Sami Albion Manager · {__version__}")
        labels = [label.text() for label in self.window.findChildren(QLabel)]
        self.assertIn("SERVEUR EUROPE", labels)
        self.assertNotIn("●  SERVEUR EUROPE", labels)

    def test_artisan_banner_only_shows_new_title(self):
        import inspect
        from samialbion.ui_calculator import TavernBanner
        source = inspect.getsource(TavernBanner.paintEvent)
        self.assertIn("MON CARNET D’ARTISAN", source)
        self.assertNotIn("LE COMPTOIR DU RÉCOLTEUR", source)
        self.assertNotIn("CARNET D'ARTISAN  ·  ROYAUME D'ALBION", source)

    def test_crafting_table_can_select_recipe_and_calculate(self):
        self.window.crafting_button.click()
        self.assertEqual(self.window.pages.currentWidget(), self.window.crafting_page)
        page = self.window.crafting_page
        page.search.setText("épée large de l'adepte")
        page._refresh_search()
        self.assertGreater(page.results.count(), 0)
        row = next(index for index in range(page.results.count())
                   if page.results.item(index).data(Qt.ItemDataRole.UserRole) == "T4_MAIN_SWORD")
        page.results.setCurrentRow(row)
        self.assertEqual(page.selected.item_id, "T4_MAIN_SWORD")
        self.assertEqual(len(page.material_inputs), 2)
        page.material_inputs["T4_METALBAR"].setValue(100)
        page.material_inputs["T4_LEATHER"].setValue(200)
        page.sale_price.setValue(5000)
        page.market_tax.setChecked(False)
        page.artisan_fee.setValue(0)
        page.return_rate.setValue(0)
        page.target_units.setValue(2)
        self.assertIn("3 600", page.profit.text())
        self.assertIn("56.2", page.roi.text())
        self.assertIn("× 32", page.material_quantities["T4_METALBAR"].text())
        page.market_tax.setChecked(True)
        page.artisan_fee.setValue(100)
        page.return_rate.setValue(20)
        self.assertIn("4 030", page.profit.text())
        self.assertIn("−650", page.breakdown.text())
        self.assertIn("−200", page.breakdown.text())
        self.window.catalogue_button.click()
        self.assertEqual(self.window.pages.currentWidget(), self.window.catalogue_page)

    def test_crafting_numeric_inputs_have_readable_dark_text(self):
        self.window.crafting_button.click()
        page = self.window.crafting_page
        controls = (page.sale_price, page.target_units, page.artisan_fee, page.return_rate)
        page.search.setText("épée large de l'adepte")
        page._refresh_search()
        row = next(index for index in range(page.results.count())
                   if page.results.item(index).data(Qt.ItemDataRole.UserRole) == "T4_MAIN_SWORD")
        page.results.setCurrentRow(row)
        controls += tuple(page.material_inputs.values())
        for control in controls:
            editor = control._visible_editor
            self.assertEqual(editor.objectName(), "craftVisibleNumber")
            self.assertIn("color: #382517", editor.styleSheet())
            self.assertFalse(editor.isHidden())
            expected = min(23, control.maximum())
            control.setValue(expected)
            self.assertIn(str(expected), editor.text())
            self.assertIn(str(expected), control.text())

    def test_craft_number_has_visible_dark_pixels_on_parchment(self):
        # Unlike checking only the stylesheet, inspect the actual Qt-painted
        # control. This catches invisible text with a light Qt palette.
        self.window.crafting_button.click()
        page = self.window.crafting_page
        box = page.sale_price
        box.setValue(123456)
        self.app.processEvents()
        image = box._visible_editor.grab().toImage()
        dark_pixels = 0
        for y in range(8, max(9, image.height() - 8)):
            for x in range(16, max(17, min(150, image.width() - 16))):
                color = image.pixelColor(x, y)
                if color.red() < 125 and color.green() < 125 and color.blue() < 125:
                    dark_pixels += 1
        self.assertGreater(dark_pixels, 12, "Craft input text must be visibly dark")

    def test_typing_into_visible_craft_field_updates_calculations(self):
        self.window.crafting_button.click()
        page = self.window.crafting_page
        editor = page.sale_price._visible_editor
        editor.setFocus()
        editor.selectAll()
        QTest.keyClicks(editor, "12345")
        self.app.processEvents()
        self.assertEqual(page.sale_price.value(), 12345)
        self.assertEqual(editor.text(), "12345")
        page.sale_price.stepUp()
        editor.clearFocus()
        self.app.processEvents()
        self.assertEqual(editor.text(), str(page.sale_price.value()))

    def test_craft_search_reset_does_not_clear_profitability(self):
        self.window.crafting_button.click()
        page = self.window.crafting_page
        page.search.setText("épée large de l'adepte")
        page.tier.setCurrentIndex(4)
        page.enchant.setCurrentIndex(1)
        page.sale_price.setValue(12345)
        page.reset_search_button.click()
        self.assertEqual(page.search.text(), "")
        self.assertEqual(page.tier.currentIndex(), 0)
        self.assertEqual(page.enchant.currentIndex(), 0)
        self.assertEqual(page.sale_price.value(), 12345)

    def test_profitability_reset_preserves_selected_item_and_filters(self):
        self.window.crafting_button.click()
        page = self.window.crafting_page
        page.search.setText("épée large de l'adepte")
        page._refresh_search()
        row = next(i for i in range(page.results.count())
                   if page.results.item(i).data(Qt.ItemDataRole.UserRole) == "T4_MAIN_SWORD")
        page.results.setCurrentRow(row)
        page.sale_price.setValue(14567)
        page.target_units.setValue(30)
        for price in page.material_inputs.values():
            price.setValue(543)
        page.market_tax.setChecked(True)
        page.artisan_fee.setValue(900)
        page.return_rate.setValue(35.5)
        page.reset_profit_button.click()
        self.assertEqual(page.selected.item_id, "T4_MAIN_SWORD")
        self.assertEqual(page.search.text(), "épée large de l'adepte")
        self.assertEqual(page.sale_price.value(), 0)
        self.assertEqual(page.sale_price._visible_editor.text(), "0")
        self.assertEqual(page.target_units.value(), 1)
        self.assertTrue(all(price.value() == 0 for price in page.material_inputs.values()))
        self.assertEqual(page.artisan_fee.value(), 0)
        self.assertEqual(page.return_rate.value(), 0)
        self.assertFalse(page.market_tax.isChecked())
        self.assertFalse(hasattr(page, "tax_status"))

    def test_tax_checkbox_without_redundant_status_label(self):
        self.window.crafting_button.click()
        page = self.window.crafting_page
        self.assertFalse(hasattr(page, "tax_status"))
        page.market_tax.setChecked(False)
        self.assertFalse(page.market_tax.isChecked())
        page.market_tax.setChecked(True)
        self.assertTrue(page.market_tax.isChecked())
        self.assertTrue(page.preferences.value("craft/market_tax", False, type=bool))
        page.market_tax.setChecked(False)
        self.assertFalse(page.market_tax.isChecked())
        self.assertFalse(page.preferences.value("craft/market_tax", True, type=bool))

    def test_market_filters_have_custom_dropdown_arrow(self):
        self.window.crafting_button.click()
        from samialbion.catalogue_page import MarketFilterComboBox
        page = self.window.crafting_page
        self.assertIsInstance(page.tier, MarketFilterComboBox)
        self.assertIsInstance(page.enchant, MarketFilterComboBox)
        self.assertTrue(page.tier.isEnabled())

    def test_selected_craft_icon_has_no_recolouring(self):
        self.window.crafting_button.click()
        page = self.window.crafting_page
        self.assertGreater(page.results.count(), 0)
        icon = page.results.item(0).icon()
        from PySide6.QtGui import QIcon
        normal = icon.pixmap(40, 40, QIcon.Mode.Normal).toImage()
        selected = icon.pixmap(40, 40, QIcon.Mode.Selected).toImage()
        self.assertEqual(normal.size(), selected.size())
        for y in range(0, normal.height(), 3):
            for x in range(0, normal.width(), 3):
                self.assertEqual(normal.pixel(x, y), selected.pixel(x, y))

    def test_sound_and_its_setting_are_completely_removed(self):
        self.assertFalse(hasattr(self.window, "click_sound"))
        self.assertFalse(hasattr(self.window, "click_sound_checkbox"))
        labels = [label.text() for label in self.window.findChildren(QLabel)]
        self.assertNotIn("Sons de l'interface", labels)
        self.assertEqual(self.window.updates_button.text(), "↻   Mises à jour")

    def test_clean_workshop_without_status_bar_or_descriptions(self):
        self.assertFalse(hasattr(self.window, "status"))
        labels = [label.text() for label in self.window.findChildren(QLabel)]
        self.assertFalse(any("On reconstruit" in text for text in labels))
        self.assertFalse(any("Première fonction" in text for text in labels))

    def test_header_illustration_is_available(self):
        self.assertFalse(self.window.banner.banner_image.isNull())

    def test_backspace_deletes_search_text_not_calculator_digits(self):
        self.app.installEventFilter(self.window)
        try:
            search = self.window.catalogue_page.search
            search.setFocus()
            QTest.keyClicks(search, "grand marte")
            QTest.keyClick(search, Qt.Key.Key_Backspace)
            self.assertEqual(search.text(), "grand mart")
            self.assertEqual(self.window.drawer.value.text(), "0")
            QTest.keyClick(search, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
            QTest.keyClick(search, Qt.Key.Key_Delete)
            self.assertEqual(search.text(), "")
        finally:
            self.app.removeEventFilter(self.window)

    def test_calculator_keyboard_works_when_drawer_is_focused(self):
        self.app.installEventFilter(self.window)
        try:
            self.window.toggle_calculator(animate=False)
            self.window.drawer.setFocus()
            QTest.keyClick(self.window.drawer, Qt.Key.Key_7)
            QTest.keyClick(self.window.drawer, Qt.Key.Key_Plus)
            QTest.keyClick(self.window.drawer, Qt.Key.Key_2)
            QTest.keyClick(self.window.drawer, Qt.Key.Key_Return)
            self.assertEqual(self.window.drawer.value.text(), "9")
        finally:
            self.app.removeEventFilter(self.window)


if __name__ == "__main__":
    unittest.main()
