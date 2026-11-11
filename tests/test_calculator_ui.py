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

    def test_github_updates_button_is_available(self):
        self.assertEqual(self.window.updates_button.text(), "↻   Mises à jour")
        self.assertIsNotNone(self.window.update_controller)
        self.assertEqual(self.window.pages.currentWidget(), self.window.catalogue_page)
        self.window.settings_button.click()
        self.assertEqual(self.window.pages.currentWidget(), self.window.settings_page)
        self.assertTrue(self.window.updates_button.isVisible())
        self.window.catalogue_button.click()
        self.assertEqual(self.window.pages.currentWidget(), self.window.catalogue_page)

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
