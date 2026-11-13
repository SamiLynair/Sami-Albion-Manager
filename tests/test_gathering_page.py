"""Headless UI tests for the gathering demo page (no game connection)."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from samialbion.gathering_page import GatheringPage
except ImportError:
    QApplication = None


@unittest.skipUnless(QApplication is not None, "PySide6 is not installed")
class GatheringPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = TemporaryDirectory()
        self.path = Path(self.folder.name) / "gather_demo.db"
        self.page = GatheringPage(database_path=self.path)
        self.page.show()
        self.app.processEvents()

    def tearDown(self):
        self.page.close()
        self.folder.cleanup()

    def test_empty_demo_is_explicit_and_cannot_simulate_without_session(self):
        self.assertEqual(self.page.session_picker.count(), 0)
        self.assertFalse(self.page.simulate_button.isEnabled())
        self.assertFalse(self.page.end_button.isEnabled())
        self.assertIn("DÉMONSTRATION", self.page.findChildren(
            type(self.page.message))[0].parentWidget().findChild(
            type(self.page.message), "gatheringCaution").text())

    def test_simulation_populates_original_icon_table_and_metrics(self):
        self.page.character_input.setText("Testeur")
        self.page.start_button.click()
        self.assertEqual(self.page.session_picker.count(), 1)
        self.assertTrue(self.page.simulate_button.isEnabled())

        self.page.simulate_button.click()
        self.page.simulate_button.click()
        self.assertEqual(self.page.total_value.text(), "10")
        self.assertEqual(self.page.event_value.text(), "2")
        self.assertEqual(self.page.table.rowCount(), 2)
        self.assertEqual(self.page.table.item(0, 4).text(), "5")
        self.assertEqual(self.page.table.item(1, 4).text(), "5")
        first_resource = self.page.table.item(0, 0)
        self.assertTrue(first_resource.text())
        self.assertFalse(first_resource.icon().isNull())
        self.assertEqual(self.page.store.summary(
            self.page.session_picker.currentData()).total_resources, 10)

    def test_ended_session_is_read_only_and_survives_reopening(self):
        self.page.character_input.setText("Sami")
        self.page.start_button.click()
        self.page.simulate_button.click()
        self.page.end_button.click()
        self.assertFalse(self.page.simulate_button.isEnabled())
        self.assertFalse(self.page.end_button.isEnabled())
        self.page.close()
        self.page = GatheringPage(database_path=self.path)
        self.page.show()
        self.app.processEvents()
        self.assertEqual(self.page.total_value.text(), "5")
        self.assertEqual(self.page.session_picker.count(), 1)
        self.assertFalse(self.page.simulate_button.isEnabled())

    def test_start_requires_character_name(self):
        self.page.start_button.click()
        self.assertEqual(self.page.session_picker.count(), 0)
        self.assertIn("nom du personnage", self.page.message.text())


if __name__ == "__main__":
    unittest.main()
