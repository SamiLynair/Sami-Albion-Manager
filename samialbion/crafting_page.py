"""Manual-price crafting profitability workbench."""

from __future__ import annotations

from PySide6.QtCore import QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDoubleSpinBox, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QAbstractSpinBox, QScrollArea, QSpinBox, QVBoxLayout,
    QWidget,
)

from .catalogue_page import MarketFilterComboBox
from .crafting import CraftingRecipes, calculate_profit
from .inventory_catalog import OfflineItemCatalog, fold
from .item_icons import OfflineIconStore


def silver(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " argent"


class CraftingPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.catalog = OfflineItemCatalog()
        self.recipes = CraftingRecipes()
        self.icons = OfflineIconStore()
        self.preferences = QSettings("Sami", "SamiAlbionManager")
        self.craftables = [item for item in self.catalog.items if item.item_id in self.recipes.by_id]
        self.selected = None
        self.material_inputs: dict[str, QSpinBox] = {}
        self.material_subtotals: dict[str, QLabel] = {}
        self.material_quantities: dict[str, QLabel] = {}
        self._build()
        self._refresh_search()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)
        heading = QLabel("TABLE DE CRAFT")
        heading.setObjectName("catalogueTitle")
        root.addWidget(heading)
        subtitle = QLabel("Recettes d'Albion · Matières premières · Frais, taxes et bénéfice net estimé")
        subtitle.setObjectName("catalogueSubtitle")
        root.addWidget(subtitle)

        body = QHBoxLayout()
        body.setSpacing(12)
        finder = QFrame()
        finder.setObjectName("craftPanel")
        finder.setMinimumWidth(310)
        finder.setMaximumWidth(460)
        finder_col = QVBoxLayout(finder)
        finder_col.setContentsMargins(15, 16, 15, 15)
        finder_col.setSpacing(10)
        finder_col.addWidget(self._label("CHOISIR UN OBJET", "detailCaption"))
        self.search = QLineEdit()
        self.search.setObjectName("catalogueSearch")
        self.search.setPlaceholderText("Rechercher un objet à fabriquer…")
        finder_col.addWidget(self.search)
        filters = QHBoxLayout()
        self.tier = MarketFilterComboBox()
        self.tier.setObjectName("craftFilter")
        self.tier.addItem("Tous les tiers", None)
        for tier in range(1, 9):
            self.tier.addItem(f"Tier {tier}", tier)
        filters.addWidget(self.tier)
        self.enchant = MarketFilterComboBox()
        self.enchant.setObjectName("craftFilter")
        self.enchant.addItem("Tous les enchant.", None)
        for enchant in range(5):
            self.enchant.addItem(f"Enchantement .{enchant}", enchant)
        filters.addWidget(self.enchant)
        finder_col.addLayout(filters)
        self.found = QLabel()
        self.found.setObjectName("catalogueSubtitle")
        finder_col.addWidget(self.found)
        self.results = QListWidget()
        self.results.setObjectName("craftResults")
        self.results.setIconSize(QSize(40, 40))
        self.results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results.currentItemChanged.connect(self._choose_item)
        finder_col.addWidget(self.results, 1)
        body.addWidget(finder, 2)

        details_scroll = QScrollArea()
        details_scroll.setWidgetResizable(True)
        details_scroll.setFrameShape(QFrame.Shape.NoFrame)
        details_scroll.setObjectName("craftScroll")
        details = QFrame()
        details.setObjectName("craftPanel")
        detail_col = QVBoxLayout(details)
        detail_col.setContentsMargins(17, 12, 17, 12)
        detail_col.setSpacing(7)
        detail_col.addWidget(self._label("RECETTE ET RENTABILITÉ", "detailCaption"))
        selected_row = QHBoxLayout()
        self.item_icon = QLabel()
        self.item_icon.setFixedSize(56, 56)
        selected_row.addWidget(self.item_icon)
        names = QVBoxLayout()
        self.item_name = self._label("Sélectionne un objet à gauche", "detailName")
        self.item_name.setWordWrap(True)
        names.addWidget(self.item_name)
        self.recipe_note = self._label("Les ressources apparaîtront ici.", "catalogueSubtitle")
        self.recipe_note.setWordWrap(True)
        names.addWidget(self.recipe_note)
        selected_row.addLayout(names, 1)
        detail_col.addLayout(selected_row)

        self.material_title = self._label("RESSOURCES NÉCESSAIRES", "detailCaption")
        detail_col.addWidget(self.material_title)
        self.materials_frame = QWidget()
        self.materials_layout = QGridLayout(self.materials_frame)
        self.materials_layout.setContentsMargins(0, 2, 0, 2)
        self.materials_layout.setHorizontalSpacing(12)
        self.materials_layout.setVerticalSpacing(8)
        detail_col.addWidget(self.materials_frame)

        sell_panel = QFrame()
        sell_panel.setObjectName("craftPricePanel")
        sell_layout = QGridLayout(sell_panel)
        sell_layout.setContentsMargins(15, 12, 15, 12)
        sell_layout.addWidget(self._label("Prix de vente unitaire au marché", "craftField"), 0, 0)
        self.sale_price = self._price_input("Prix de vente")
        self.sale_price.valueChanged.connect(self._price_changed)
        sell_layout.addWidget(self._with_step_buttons(self.sale_price), 0, 1)
        sell_layout.addWidget(self._label("Quantité d'objets souhaitée", "craftField"), 1, 0)
        self.target_units = QSpinBox()
        self.target_units.setObjectName("craftNumber")
        self.target_units.setAccessibleName("Quantité d'objets à fabriquer")
        self.target_units.setRange(1, 1_000_000)
        self.target_units.setValue(1)
        self.target_units.valueChanged.connect(self._recalculate)
        sell_layout.addWidget(self._with_step_buttons(self.target_units), 1, 1)
        self.production_note = self._label("", "craftExplanation")
        self.production_note.setWordWrap(True)
        sell_layout.addWidget(self.production_note, 2, 0, 1, 2)
        detail_col.addWidget(sell_panel)

        fees_panel = QFrame()
        fees_panel.setObjectName("craftFeePanel")
        fees_layout = QGridLayout(fees_panel)
        fees_layout.setContentsMargins(15, 12, 15, 12)
        fees_layout.setVerticalSpacing(11)
        fees_layout.addWidget(self._label("TAXES ET BONUS", "detailCaption"), 0, 0, 1, 2)
        self.market_tax = QCheckBox("Déduire 6,5 % sur la vente au marché")
        self.market_tax.setObjectName("craftCheckbox")
        self.market_tax.setChecked(self.preferences.value("craft/market_tax", False, type=bool))
        self.market_tax.toggled.connect(self._options_changed)
        fees_layout.addWidget(self.market_tax, 1, 0, 1, 2)
        fees_layout.addWidget(self._label("Coût d'artisan par fabrication", "craftField"), 2, 0)
        self.artisan_fee = self._price_input("Coût de l'artisan par fabrication")
        self.artisan_fee.setValue(int(self.preferences.value("craft/artisan_fee", 0)))
        self.artisan_fee.valueChanged.connect(self._options_changed)
        fees_layout.addWidget(self._with_step_buttons(self.artisan_fee), 2, 1)
        fees_layout.addWidget(self._label("Retour de ressources (%)", "craftField"), 3, 0)
        self.return_rate = QDoubleSpinBox()
        self.return_rate.setObjectName("craftNumber")
        self.return_rate.setAccessibleName("Pourcentage de retour des ressources")
        self.return_rate.setRange(0, 100)
        self.return_rate.setDecimals(1)
        self.return_rate.setSingleStep(1)
        self.return_rate.setSuffix("  %")
        self.return_rate.setValue(float(self.preferences.value("craft/return_rate", 0)))
        self.return_rate.valueChanged.connect(self._options_changed)
        fees_layout.addWidget(self._with_step_buttons(self.return_rate), 3, 1)
        detail_col.addWidget(fees_panel)

        self.breakdown = self._label("", "craftBreakdown")
        self.breakdown.setWordWrap(True)
        detail_col.addWidget(self.breakdown)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(10)
        metrics.setVerticalSpacing(9)
        self.cost = self._metric(metrics, 0, 0, "COÛT NET DES RESSOURCES")
        self.revenue = self._metric(metrics, 0, 1, "VALEUR DE VENTE")
        self.profit = self._metric(metrics, 1, 0, "BÉNÉFICE APRÈS FRAIS")
        self.roi = self._metric(metrics, 1, 1, "RENTABILITÉ / COÛT")
        detail_col.addLayout(metrics)
        self.disclaimer = self._label(
            "Simulation : retour de ressources valorisé au prix saisi ; la quantité initiale complète "
            "reste nécessaire pour lancer le craft. Les taxes sont calculées sur la vente totale. "
            "Les prix et options sont mémorisés sur ce PC.", "catalogueSubtitle"
        )
        self.disclaimer.setWordWrap(True)
        detail_col.addWidget(self.disclaimer)
        detail_col.addStretch(1)
        details_scroll.setWidget(details)
        body.addWidget(details_scroll, 3)
        root.addLayout(body, 1)

        self.search_delay = QTimer(self)
        self.search_delay.setSingleShot(True)
        self.search_delay.setInterval(100)
        self.search_delay.timeout.connect(self._refresh_search)
        self.search.textChanged.connect(lambda _: self.search_delay.start())
        self.tier.currentIndexChanged.connect(self._refresh_search)
        self.enchant.currentIndexChanged.connect(self._refresh_search)
        self._recalculate()

    @staticmethod
    def _label(text, object_name):
        label = QLabel(text)
        label.setObjectName(object_name)
        return label

    @staticmethod
    def _price_input(accessible_name):
        control = QSpinBox()
        control.setObjectName("craftNumber")
        control.setAccessibleName(accessible_name)
        control.setRange(0, 1_000_000_000)
        control.setGroupSeparatorShown(True)
        control.setSuffix("  argent")
        control.setSingleStep(100)
        return control

    @staticmethod
    def _with_step_buttons(control):
        """Show compact, readable minus/plus buttons instead of native spin arrows."""
        control.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(3)
        row.addWidget(control, 1)
        for symbol, direction in (("−", -1), ("+", 1)):
            button = QPushButton(symbol)
            button.setObjectName("craftStepButton")
            button.setAccessibleName(("Diminuer " if direction < 0 else "Augmenter ") + control.accessibleName())
            button.setFixedSize(24, 27)
            button.setAutoRepeat(True)
            button.clicked.connect(control.stepDown if direction < 0 else control.stepUp)
            row.addWidget(button)
        return holder

    def _metric(self, grid, row, column, caption):
        panel = QFrame()
        panel.setObjectName("craftMetric")
        col = QVBoxLayout(panel)
        col.setContentsMargins(13, 12, 13, 12)
        col.addWidget(self._label(caption, "craftMetricCaption"))
        value = self._label("—", "craftMetricValue")
        value.setWordWrap(True)
        col.addWidget(value)
        grid.addWidget(panel, row, column)
        return value

    def _refresh_search(self, *_):
        query = fold(self.search.text()).split()
        tier = self.tier.currentData()
        enchantment = self.enchant.currentData()
        matching = [
            item for item in self.craftables
            if (not query or all(term in item.search_text for term in query))
            and (tier is None or item.tier == tier)
            and (enchantment is None or item.enchantment == enchantment)
        ]
        self.found.setText(f"{len(matching):,} recettes disponibles · 100 affichées max.".replace(",", " "))
        selected_id = self.selected.item_id if self.selected else None
        self.results.blockSignals(True)
        self.results.clear()
        selected_row = -1
        for position, item in enumerate(matching[:100]):
            label = f"{item.name}   ·   T{item.tier}.{item.enchantment}" if item.tier else item.name
            row = QListWidgetItem(self.icons.icon(item.item_id).pixmap(40, 40, QIcon.Mode.Normal), label)
            row.setData(Qt.ItemDataRole.UserRole, item.item_id)
            self.results.addItem(row)
            if item.item_id == selected_id:
                selected_row = position
        if selected_row >= 0:
            self.results.setCurrentRow(selected_row)
        self.results.blockSignals(False)

    def _choose_item(self, current, _previous):
        if current is None:
            return
        item = self.catalog.by_id[current.data(Qt.ItemDataRole.UserRole)]
        self.selected = item
        recipe = self.recipes.by_id[item.item_id]
        self.item_name.setText(item.name)
        self.item_icon.setPixmap(self.icons.icon(item.item_id).pixmap(54, 54, QIcon.Mode.Normal))
        output = f"{recipe.output_amount} unité(s) produite(s) par fabrication"
        if item.tier:
            output += f" · T{item.tier}.{item.enchantment}"
        self.recipe_note.setText(output)

        while self.materials_layout.count():
            child = self.materials_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.material_inputs.clear()
        self.material_subtotals.clear()
        self.material_quantities.clear()
        for column, heading in enumerate(("Ressource", "À prévoir", "Prix unitaire", "Total à acheter")):
            self.materials_layout.addWidget(self._label(heading, "craftField"), 0, column)
        for index, (material_id, amount) in enumerate(recipe.materials, 1):
            resource = self.catalog.by_id.get(material_id)
            name = resource.name if resource else "Ressource indisponible"
            icon = QLabel()
            icon.setPixmap(self.icons.icon(material_id).pixmap(32, 32, QIcon.Mode.Normal))
            cell = QWidget()
            line = QHBoxLayout(cell)
            line.setContentsMargins(0, 0, 0, 0)
            line.setSpacing(5)
            line.addWidget(icon)
            name_label = self._label(name, "craftResource")
            name_label.setWordWrap(True)
            line.addWidget(name_label, 1)
            self.materials_layout.addWidget(cell, index, 0)
            quantity_label = self._label(f"× {amount}", "craftField")
            self.materials_layout.addWidget(quantity_label, index, 1)
            control = self._price_input(f"Prix de {name}")
            control.setValue(int(self.preferences.value(f"craft/material/{material_id}", 0)))
            control.valueChanged.connect(lambda value, key=material_id: self._material_price_changed(key, value))
            self.materials_layout.addWidget(self._with_step_buttons(control), index, 2)
            subtotal = self._label("0", "craftResource")
            self.materials_layout.addWidget(subtotal, index, 3)
            self.material_inputs[material_id] = control
            self.material_subtotals[material_id] = subtotal
            self.material_quantities[material_id] = quantity_label
        self.sale_price.blockSignals(True)
        self.sale_price.setValue(int(self.preferences.value(f"craft/sale/{item.item_id}", 0)))
        self.sale_price.blockSignals(False)
        self.target_units.blockSignals(True)
        self.target_units.setValue(recipe.output_amount)
        self.target_units.blockSignals(False)
        self._recalculate()

    def _material_price_changed(self, key, value):
        self.preferences.setValue(f"craft/material/{key}", value)
        self._recalculate()

    def _price_changed(self, value):
        if self.selected:
            self.preferences.setValue(f"craft/sale/{self.selected.item_id}", value)
        self._recalculate()

    def _options_changed(self, *_):
        self.preferences.setValue("craft/market_tax", self.market_tax.isChecked())
        self.preferences.setValue("craft/artisan_fee", self.artisan_fee.value())
        self.preferences.setValue("craft/return_rate", self.return_rate.value())
        self._recalculate()

    def _recalculate(self, *_):
        if self.selected is None:
            for label in (self.cost, self.revenue, self.profit, self.roi):
                label.setText("—")
            return
        recipe = self.recipes.by_id[self.selected.item_id]
        prices = {key: field.value() for key, field in self.material_inputs.items()}
        result = calculate_profit(
            recipe, prices, self.sale_price.value(),
            target_units=self.target_units.value(),
            market_tax_enabled=self.market_tax.isChecked(),
            artisan_fee_per_batch=self.artisan_fee.value(),
            return_percent=self.return_rate.value(),
        )
        self.production_note.setText(
            f"{result.batches} fabrication(s) × {recipe.output_amount} = "
            f"{result.produced} objet(s) produits"
            + (" (arrondi à la fabrication supérieure)" if result.produced != self.target_units.value() else "")
        )
        for material_id, amount in recipe.materials:
            field = self.material_inputs[material_id]
            total_quantity = amount * result.batches
            self.material_quantities[material_id].setText(f"× {total_quantity:,}".replace(",", " "))
            self.material_subtotals[material_id].setText(silver(total_quantity * field.value()))
        self.breakdown.setText(
            f"Achat initial : {silver(result.upfront_cost)}  ·  "
            f"Ressources récupérées (valeur estimée) : −{silver(result.recovered_value)}\n"
            f"Taxe du marché : −{silver(result.market_fee)}  ·  "
            f"Artisan : −{silver(result.artisan_fee)}"
        )
        if not self.sale_price.value() or not all(prices.values()):
            self.cost.setText(silver(result.cost))
            self.revenue.setText(silver(result.revenue))
            self.profit.setText("Prix manquants")
            self.profit.setStyleSheet("")
            self.roi.setText("—")
            return
        self.cost.setText(silver(result.cost))
        self.revenue.setText(silver(result.revenue))
        self.profit.setText(("+" if result.profit > 0 else "") + silver(result.profit))
        self.profit.setStyleSheet("color: #266b38;" if result.profit > 0 else
                                  "color: #a13f33;" if result.profit < 0 else "")
        self.roi.setText(f"{result.roi_percent:+.1f} %" if result.roi_percent is not None else "—")

    def closeEvent(self, event):
        self.icons.close()
        super().closeEvent(event)
