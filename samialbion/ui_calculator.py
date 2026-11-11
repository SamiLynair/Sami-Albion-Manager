"""Artisan workbench with the offline item catalogue and calculator drawer."""

from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import QEvent, QEasingCurve, QPropertyAnimation, QRectF, QSettings, Qt
from PySide6.QtGui import (
    QColor, QFont, QFontDatabase, QIcon, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap,
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from . import __version__
from .calculator import Calculator
from .catalogue_page import CataloguePage
from .crafting_page import CraftingPage
from .click_sound import ClickSound
from .update_ui import UpdateController


ASSETS = Path(__file__).resolve().parent / "assets"
DISPLAY_FAMILY = "Noto Serif"
_fonts_registered = False


def load_display_fonts():
    """Bundle the workshop's display font so Windows needs no extra install."""
    global _fonts_registered
    if _fonts_registered:
        return
    for filename in ("NotoSerif-Bold.ttf",):
        font_path = ASSETS / "fonts" / filename
        if font_path.is_file():
            QFontDatabase.addApplicationFont(str(font_path))
    _fonts_registered = True


def display_font(size: int, *, bold: bool = False, tracking: float = 0) -> QFont:
    font = QFont(DISPLAY_FAMILY, size, QFont.Weight.Bold if bold else QFont.Weight.Normal)
    if tracking:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, tracking)
    return font


class TavernBanner(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(145)
        self.banner_image = QPixmap(str(ASSETS / "header_recolte.jpg"))

    def _paint_harvest_image(self, painter: QPainter):
        """Blend the supplied Albion illustration into the wood from right to left."""
        if self.banner_image.isNull():
            return

        region_width = min(700, max(360, round(self.width() * 0.62)))
        region_height = self.height() - 4
        source_height = min(
            self.banner_image.height(),
            self.banner_image.width() * region_height / region_width,
        )
        source_top = max(
            0.0,
            min(self.banner_image.height() - source_height,
                self.banner_image.height() * 0.47 - source_height / 2),
        )

        faded = QPixmap(region_width, region_height)
        faded.fill(Qt.GlobalColor.transparent)
        layer = QPainter(faded)
        layer.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        layer.drawPixmap(
            QRectF(0, 0, region_width, region_height),
            self.banner_image,
            QRectF(0, source_top, self.banner_image.width(), source_height),
        )
        layer.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        alpha = QLinearGradient(0, 0, region_width, 0)
        alpha.setColorAt(0, QColor(255, 255, 255, 0))
        alpha.setColorAt(0.23, QColor(255, 255, 255, 18))
        alpha.setColorAt(0.65, QColor(255, 255, 255, 185))
        alpha.setColorAt(1, QColor(255, 255, 255, 255))
        layer.fillRect(faded.rect(), alpha)
        layer.end()

        painter.save()
        outline = QPainterPath()
        outline.addRoundedRect(QRectF(self.rect().adjusted(1, 1, -1, -1)), 16, 16)
        painter.setClipPath(outline)
        painter.drawPixmap(self.width() - region_width - 2, 2, faded)
        painter.restore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor("#493322"))
        gradient.setColorAt(0.56, QColor("#302a20"))
        gradient.setColorAt(1, QColor("#243629"))
        painter.setPen(QPen(QColor("#866747"), 1))
        painter.setBrush(gradient)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 16, 16)
        painter.setPen(QPen(QColor(255, 226, 164, 17), 1))
        for x in range(28, self.width(), 57):
            painter.drawLine(x, 8, x + 45, self.height() - 8)
        self._paint_harvest_image(painter)
        painter.setPen(QPen(QColor("#866747"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 16, 16)
        painter.setPen(QColor("#e7c48c"))
        small_title = QFont("Segoe UI", 11, QFont.Weight.DemiBold)
        small_title.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.6)
        painter.setFont(small_title)
        painter.drawText(30, 31, "✦  CARNET D'ARTISAN  ·  ROYAUME D'ALBION")
        painter.setFont(display_font(24, bold=True, tracking=0.4))
        painter.setPen(QColor("#f9e9c8"))
        painter.drawText(30, min(97, self.height() - 23), "LE COMPTOIR DU RÉCOLTEUR")
        painter.end()


class CalculatorDrawer(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("calcDrawer")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.engine = Calculator()
        col = QVBoxLayout(self)
        col.setContentsMargins(8, 8, 8, 8)
        col.setSpacing(6)

        display_box = QFrame()
        display_box.setObjectName("calcDisplay")
        display_col = QVBoxLayout(display_box)
        display_col.setContentsMargins(8, 5, 8, 5)
        display_col.setSpacing(1)
        self.history = QLabel(" ")
        self.history.setObjectName("calcHistory")
        self.history.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.value = QLabel("0")
        self.value.setObjectName("calcValue")
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.value.setMinimumHeight(31)
        display_col.addWidget(self.history)
        display_col.addWidget(self.value)
        col.addWidget(display_box)

        grid = QGridLayout()
        grid.setSpacing(4)
        keys = (
            ("AC", "±", "%", "÷"),
            ("7", "8", "9", "×"),
            ("4", "5", "6", "−"),
            ("1", "2", "3", "+"),
            ("←", "0", ",", "="),
        )
        self.key_buttons = {}
        for row, items in enumerate(keys):
            for column, key in enumerate(items):
                button = QPushButton(key)
                button.setObjectName("calcEquals" if key == "=" else
                                     "calcOperator" if key in ("÷", "×", "−", "+") else
                                     "calcUtility" if key in ("AC", "±", "%", "←") else "calcNumber")
                button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.setMinimumHeight(33)
                button.clicked.connect(lambda checked=False, symbol=key: self.press(symbol))
                grid.addWidget(button, row, column)
                self.key_buttons[key] = button
        col.addLayout(grid)

    def press(self, key: str):
        # Mouse interaction activates calculator keyboard shortcuts; focusing
        # the catalogue search returns every keystroke to the text editor.
        self.setFocus()
        self.engine.press(key)
        self.value.setText(self.engine.display)
        self.history.setText(self.engine.history or " ")
        self.value.setStyleSheet(
            "color: #ecaaa2; font-size: 15px;" if self.engine.error else
            "font-size: 17px;" if len(self.engine.display) > 12 else ""
        )


class WorkshopWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        load_display_fonts()
        self.setWindowTitle(f"Sami Albion Manager · {__version__} — Le Comptoir du Récolteur")
        self.resize(1370, 870)
        self.setMinimumSize(1050, 720)
        self.expanded = False
        self.preferences = QSettings("Sami", "SamiAlbionManager")
        self.click_sound = ClickSound(self.preferences.value("ui/click_sound", True, type=bool))
        self._build()
        self.update_controller = UpdateController(self, self.updates_button)
        icon = Path(__file__).resolve().parents[1] / "samialbion.ico"
        if icon.is_file():
            self.setWindowIcon(QIcon(str(icon)))

    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        base = QHBoxLayout(root)
        base.setContentsMargins(0, 0, 0, 0)
        base.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sideBar")
        sidebar.setFixedWidth(238)
        side_col = QVBoxLayout(sidebar)
        side_col.setContentsMargins(16, 25, 16, 16)
        side_col.setSpacing(7)

        brand = QFrame()
        brand.setObjectName("sideBrand")
        brand_col = QVBoxLayout(brand)
        brand_col.setContentsMargins(9, 9, 3, 23)
        brand_col.setSpacing(2)
        brand_title = QLabel("✦  SAMI")
        brand_title.setObjectName("brand")
        brand_title.setFont(display_font(23, bold=True, tracking=0.6))
        brand_sub = QLabel("ALBION MANAGER")
        brand_sub.setObjectName("brandSub")
        brand_sub.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        brand_col.addWidget(brand_title)
        brand_col.addWidget(brand_sub)
        side_col.addWidget(brand)

        tools_label = QLabel("MES OUTILS")
        tools_label.setObjectName("fieldCaption")
        tools_label.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        side_col.addWidget(tools_label)

        self.catalogue_button = QPushButton("📦   Catalogue d'objets")
        self.catalogue_button.setObjectName("nav")
        self.catalogue_button.setProperty("active", "true")
        self.catalogue_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.catalogue_button.clicked.connect(self.show_catalogue)
        side_col.addWidget(self.catalogue_button)
        self.crafting_button = QPushButton("⚒   Table de Craft")
        self.crafting_button.setObjectName("nav")
        self.crafting_button.setProperty("active", "false")
        self.crafting_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.crafting_button.clicked.connect(self.show_crafting)
        side_col.addWidget(self.crafting_button)
        side_col.addStretch(1)

        self.drawer_button = QPushButton("▾  🧮  Calculatrice")
        self.drawer_button.setObjectName("drawerToggle")
        self.drawer_button.setProperty("active", False)
        self.drawer_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.drawer_button.setMinimumHeight(36)
        self.drawer_button.clicked.connect(self.toggle_calculator)
        side_col.addWidget(self.drawer_button)
        self.drawer = CalculatorDrawer()
        self.drawer.setVisible(False)
        self.drawer.setMaximumHeight(0)
        side_col.addWidget(self.drawer)
        self.drawer_anim = QPropertyAnimation(self.drawer, b"maximumHeight", self)
        self.drawer_anim.setDuration(230)
        self.drawer_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.drawer_anim.finished.connect(self._finish_animation)

        europe = QLabel("●  SERVEUR EUROPE")
        europe.setObjectName("pill")
        europe.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        europe.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side_col.addWidget(europe)

        footer = QWidget()
        footer_col = QVBoxLayout(footer)
        footer_col.setContentsMargins(2, 7, 0, 0)
        footer_col.setSpacing(0)
        self.author_label = QLabel("Made by Sami")
        self.author_label.setObjectName("footerAuthor")
        self.version_label = QLabel(f"v{__version__}")
        self.version_label.setObjectName("footerVersion")
        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(0, 0, 0, 0)
        footer_row.setSpacing(4)
        footer_row.addWidget(self.author_label)
        footer_row.addStretch()
        self.settings_button = QPushButton("⚙")
        self.settings_button.setObjectName("settingsGear")
        self.settings_button.setAccessibleName("Paramètres")
        self.settings_button.setToolTip("Paramètres")
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.setFixedSize(30, 30)
        self.settings_button.clicked.connect(self.show_settings)
        footer_row.addWidget(self.settings_button)
        footer_col.addLayout(footer_row)
        footer_col.addWidget(self.version_label)
        side_col.addWidget(footer)
        base.addWidget(sidebar)

        main = QWidget()
        main.setObjectName("root")
        main_col = QVBoxLayout(main)
        main_col.setContentsMargins(25, 19, 25, 19)
        main_col.setSpacing(17)
        self.banner = TavernBanner()
        main_col.addWidget(self.banner)

        self.pages = QStackedWidget()
        self.catalogue_page = CataloguePage()
        self.pages.addWidget(self.catalogue_page)
        self.crafting_page = CraftingPage()
        self.pages.addWidget(self.crafting_page)
        self.settings_page = QWidget()
        self.settings_page.setObjectName("settingsPage")
        settings_col = QVBoxLayout(self.settings_page)
        settings_col.setContentsMargins(0, 0, 0, 0)
        settings_col.setSpacing(14)
        title = QLabel("PARAMÈTRES")
        title.setObjectName("catalogueTitle")
        settings_col.addWidget(title)
        subtitle = QLabel("Gérer les préférences et les mises à jour du logiciel")
        subtitle.setObjectName("catalogueSubtitle")
        settings_col.addWidget(subtitle)
        sound_panel = QFrame()
        sound_panel.setObjectName("settingsPanel")
        sound_col = QVBoxLayout(sound_panel)
        sound_col.setContentsMargins(22, 17, 22, 17)
        sound_title = QLabel("Sons de l'interface")
        sound_title.setObjectName("sectionTitle")
        sound_col.addWidget(sound_title)
        self.click_sound_checkbox = QCheckBox("Jouer un léger clic lors des interactions")
        self.click_sound_checkbox.setObjectName("clickSoundCheckbox")
        self.click_sound_checkbox.setChecked(self.click_sound.enabled)
        self.click_sound_checkbox.toggled.connect(self._set_click_sound_enabled)
        sound_col.addWidget(self.click_sound_checkbox)
        settings_col.addWidget(sound_panel)
        update_panel = QFrame()
        update_panel.setObjectName("settingsPanel")
        update_col = QVBoxLayout(update_panel)
        update_col.setContentsMargins(22, 20, 22, 20)
        update_col.setSpacing(13)
        update_title = QLabel("Mises à jour de l'application")
        update_title.setObjectName("sectionTitle")
        update_col.addWidget(update_title)
        update_description = QLabel(
            "Le logiciel recherche automatiquement les nouvelles versions au démarrage. "
            "Tu peux également vérifier leur disponibilité ici."
        )
        update_description.setWordWrap(True)
        update_description.setObjectName("catalogueSubtitle")
        update_col.addWidget(update_description)
        installed_version = QLabel(f"Version installée : v{__version__}")
        installed_version.setObjectName("settingsVersion")
        update_col.addWidget(installed_version)
        self.updates_button = QPushButton("↻   Mises à jour")
        self.updates_button.setObjectName("primary")
        self.updates_button.setCursor(Qt.CursorShape.PointingHandCursor)
        update_col.addWidget(self.updates_button, 0, Qt.AlignmentFlag.AlignLeft)
        settings_col.addWidget(update_panel)
        settings_col.addStretch(1)
        self.pages.addWidget(self.settings_page)
        main_col.addWidget(self.pages, 1)
        base.addWidget(main, 1)

    def _set_click_sound_enabled(self, enabled: bool):
        self.click_sound.enabled = enabled
        self.preferences.setValue("ui/click_sound", enabled)

    def _set_active_navigation(self, current: str):
        for name, button in (("catalogue", self.catalogue_button),
                             ("crafting", self.crafting_button),
                             ("settings", self.settings_button)):
            button.setProperty("active", "true" if current == name else "false")
            button.style().unpolish(button)
            button.style().polish(button)

    def show_catalogue(self):
        self.banner.setFixedHeight(145)
        self.pages.setCurrentWidget(self.catalogue_page)
        self._set_active_navigation("catalogue")
        self.catalogue_page.search.setFocus()

    def show_crafting(self):
        self.banner.setFixedHeight(95)
        self.pages.setCurrentWidget(self.crafting_page)
        self._set_active_navigation("crafting")
        self.crafting_page.search.setFocus()

    def show_settings(self):
        self.banner.setFixedHeight(145)
        self.pages.setCurrentWidget(self.settings_page)
        self._set_active_navigation("settings")

    def toggle_calculator(self, checked=False, *, animate=True):
        opening = not self.expanded
        self.expanded = opening
        self.drawer_button.setText("▴  🧮  Calculatrice" if opening else "▾  🧮  Calculatrice")
        self.drawer_button.setProperty("active", opening)
        self.drawer_button.style().unpolish(self.drawer_button)
        self.drawer_button.style().polish(self.drawer_button)
        self.drawer_anim.stop()
        current = self.drawer.maximumHeight()
        target = self.drawer.sizeHint().height() if opening else 0
        if opening:
            self.drawer.setVisible(True)
            self.drawer.setFocus()
        if not animate:
            self.drawer.setMaximumHeight(target)
            self.drawer.setVisible(opening)
            return
        self.drawer_anim.setStartValue(current)
        self.drawer_anim.setEndValue(target)
        self.drawer_anim.start()

    def _finish_animation(self):
        if not self.expanded:
            self.drawer.setVisible(False)

    def closeEvent(self, event):
        if not self.update_controller.stop_workers():
            event.ignore()
            return
        super().closeEvent(event)

    def eventFilter(self, watched, event):
        if (event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.LeftButton
                and self.isVisible()):
            self.click_sound.play()
        if event.type() == QEvent.Type.KeyPress and self.expanded:
            focus = QApplication.focusWidget()
            # Only the explicitly focused calculator receives arithmetic
            # shortcuts. Backspace/Delete can never steal search-field input.
            if focus is None or (focus is not self.drawer and
                                  not self.drawer.isAncestorOf(focus)):
                return super().eventFilter(watched, event)
            if isinstance(watched, (QLineEdit, QComboBox)):
                return super().eventFilter(watched, event)
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                if event.key() == Qt.Key.Key_C:
                    QApplication.clipboard().setText(self.drawer.engine.display)
                    return True
                return False
            mapping = {"*": "×", "/": "÷", "-": "−", ".": ",", ",": ",",
                       "=": "=", "+": "+", "%": "%"}
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                symbol = "="
            elif event.key() == Qt.Key.Key_Backspace:
                symbol = "←"
            elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Escape):
                symbol = "AC"
            else:
                symbol = mapping.get(event.text(), event.text())
            if (len(symbol) == 1 and symbol in "0123456789+,−×÷=%") or symbol in ("←", "AC"):
                self.drawer.press(symbol)
                return True
        return super().eventFilter(watched, event)


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Sami Albion Manager")
    app.setStyle("Fusion")
    load_display_fonts()
    app.setStyleSheet((ASSETS / "tavern.qss").read_text(encoding="utf-8"))
    window = WorkshopWindow()
    app.installEventFilter(window)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
