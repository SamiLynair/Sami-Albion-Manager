"""Responsive, searchable offline item browser. No live data connections."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QFrame, QGridLayout,
    QHeaderView, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton,
    QStyledItemDelegate, QStyle, QStyleOptionViewItem, QTableView,
    QVBoxLayout, QWidget,
)

from .inventory_catalog import QUALITIES, GameItem, OfflineItemCatalog
from .item_icons import OfflineIconStore
from .market_taxonomy import MARKET_ROOTS

WEAPON_ORDER = (
    "Arc", "Arbalète", "Hache", "Dague", "Marteau", "Gants de guerre",
    "Masse", "Long bâton", "Lance", "Épée", "Bâton ésotérique",
    "Bâton damné", "Bâton de feu", "Bâton de givre", "Bâton béni",
    "Bâton naturel", "Bâton métamorphe",
)
ARC_ORDER = (
    "Arc", "Arc long", "Arc de guerre", "Arc murmurant", "Arc gémissant",
    "Arc de Badon", "Perce-brume", "Arc Marche-ciel",
)


def _market_order(options, preferred):
    priority = {name.casefold(): index for index, name in enumerate(preferred)}
    return sorted(options, key=lambda text: (priority.get(text.casefold(), len(priority)), text.casefold()))


class ItemsTableModel(QAbstractTableModel):
    HEADERS = ("Objet", "Tier", "Enchant.", "Qualité", "Type")

    def __init__(self, store: OfflineIconStore):
        super().__init__()
        self.items: list[GameItem] = []
        self.store = store
        self.selected_quality: int | None = None

    def update(self, items: list[GameItem], quality: int | None):
        self.beginResetModel()
        self.items = items
        self.selected_quality = quality
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.items)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.items)):
            return None
        item = self.items[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DecorationRole and column == 0:
            # Return the NORMAL pixmap, not QIcon. Qt otherwise synthesizes a
            # tinted Selected-mode icon whenever its table row is highlighted.
            return self.store.icon(item.item_id, self.selected_quality or 1).pixmap(
                43, 43, QIcon.Mode.Normal
            )
        if role == Qt.ItemDataRole.DisplayRole:
            if column == 0:
                return item.name
            if column == 1:
                return f"T{item.tier}" if item.tier else "—"
            if column == 2:
                return f".{item.enchantment}"
            if column == 3:
                return str(self.selected_quality) if item.has_qualities and self.selected_quality else (
                    "1 à 5" if item.has_qualities else "—"
                )
            if column == 4:
                return item.market_path[1]
        if role == Qt.ItemDataRole.TextAlignmentRole and column in (1, 2, 3):
            return Qt.AlignmentFlag.AlignCenter
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{' › '.join(item.market_path)}\n{item.item_id}"
        return None


class NeutralIconDelegate(QStyledItemDelegate):
    """Paint icons as raw normal pixmaps, independent of row selection.

    The default Qt item delegate converts DecorationRole pixmaps to QIcons
    and can apply a selected-state colour overlay even when a Normal-mode
    pixmap was supplied. We draw the selection and image independently.
    """

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        background = QStyleOptionViewItem(option)
        self.initStyleOption(background, index)
        # Let Qt draw the selected row background but never the icon/text.
        background.icon = QIcon()
        background.features &= ~QStyleOptionViewItem.ViewItemFeature.HasDecoration
        background.text = ""
        style = background.widget.style() if background.widget else QApplication.style()
        painter.save()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, background, painter, background.widget)

        pixmap = index.data(Qt.ItemDataRole.DecorationRole)
        if pixmap is not None and not pixmap.isNull():
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.drawPixmap(option.rect.left() + 9,
                               option.rect.top() + (option.rect.height() - pixmap.height()) // 2,
                               pixmap)

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.setPen(QColor("#18231b" if selected else "#ebdfc8"))
        painter.setFont(option.font)
        text_rect = option.rect.adjusted(60, 0, -8, 0)
        title = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        title = option.fontMetrics.elidedText(title, Qt.TextElideMode.ElideRight, max(0, text_rect.width()))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, title)
        painter.restore()


class CataloguePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.catalogue = OfflineItemCatalog()
        self.icons = OfflineIconStore()
        self.model = ItemsTableModel(self.icons)
        self.market_path: tuple[str, ...] | None = None
        self._build()
        self._refresh()

    def _select(self, title: str, choices: list[tuple[str, object]]) -> QComboBox:
        combo = QComboBox()
        combo.setObjectName("catalogueFilter")
        combo.setMinimumHeight(37)
        for label, value in choices:
            combo.addItem(label, value)
        combo.setAccessibleName(title)
        combo.currentIndexChanged.connect(self._refresh)
        return combo

    def _select_market_path(self, selected: tuple[str, ...] | None):
        self.market_path = selected
        self.category_button.setText(" › ".join(selected) if selected else "Toutes les catégories")
        self.category_button.setToolTip(" › ".join(selected) if selected else "Afficher toutes les catégories")
        self._refresh()

    def _open_leaf_menu(self, submenu: QMenu, root: str, group: str, families: tuple[str, ...]):
        # Build large lists on demand so opening the main menu stays instant.
        if submenu.property("populated"):
            return
        submenu.setProperty("populated", True)
        for family in families:
            action = submenu.addAction(family)
            action.triggered.connect(lambda checked=False, path=(root, group, family):
                                     self._select_market_path(path))

    def _make_market_menu(self) -> QMenu:
        hierarchy: dict[str, dict[str, set[str]]] = {}
        for item in self.catalogue.items:
            root, group, family = item.market_path
            hierarchy.setdefault(root, {}).setdefault(group, set()).add(family)

        menu = QMenu(self)
        menu.setObjectName("marketMenu")
        all_action = menu.addAction("Tout afficher")
        all_action.triggered.connect(lambda: self._select_market_path(None))
        menu.addSeparator()
        for root in MARKET_ROOTS:
            if root not in hierarchy:
                continue
            root_menu = menu.addMenu(root)
            root_menu.setObjectName("marketMenu")
            root_all = root_menu.addAction(f"Tout · {root}")
            root_all.triggered.connect(lambda checked=False, path=(root,):
                                       self._select_market_path(path))
            root_menu.addSeparator()
            group_preference = WEAPON_ORDER if root == "Armes" else (
                ("Tissu", "Cuir", "Plaque", "Spécial") if root.startswith("Armure") else ())
            for group in _market_order(hierarchy[root], group_preference):
                sub_menu = root_menu.addMenu(group)
                sub_menu.setObjectName("marketMenu")
                group_all = sub_menu.addAction(f"Tout · {group}")
                group_all.triggered.connect(lambda checked=False, path=(root, group):
                                            self._select_market_path(path))
                sub_menu.addSeparator()
                family_preference = ARC_ORDER if (root, group) == ("Armes", "Arc") else ()
                families = tuple(_market_order(hierarchy[root][group], family_preference))
                sub_menu.aboutToShow.connect(
                    lambda target=sub_menu, a=root, b=group, names=families:
                    self._open_leaf_menu(target, a, b, names)
                )
        return menu

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(13)

        top = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(3)
        title = QLabel("CATALOGUE DES OBJETS")
        title.setObjectName("catalogueTitle")
        subtitle = QLabel("Équipements · Ressources · Consommables · Montures · Artéfacts")
        subtitle.setObjectName("catalogueSubtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        top.addLayout(titles)
        top.addStretch()
        self.counter = QLabel("")
        self.counter.setObjectName("catalogueCount")
        top.addWidget(self.counter)
        layout.addLayout(top)

        filters = QFrame()
        filters.setObjectName("catalogueFilters")
        filters_layout = QGridLayout(filters)
        filters_layout.setContentsMargins(13, 12, 13, 12)
        filters_layout.setHorizontalSpacing(9)
        filters_layout.setVerticalSpacing(8)
        self.search = QLineEdit()
        self.search.setObjectName("catalogueSearch")
        self.search.setPlaceholderText("Rechercher un objet, une ressource ou un identifiant…")
        self.search.setMinimumHeight(39)
        filters_layout.addWidget(self.search, 0, 0, 1, 4)
        self.category_button = QPushButton("Toutes les catégories")
        self.category_button.setObjectName("marketCategoryButton")
        self.category_button.setMinimumHeight(37)
        self.category_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.category_button.setMenu(self._make_market_menu())
        self.tier = self._select("Tier", [("Tous les tiers", None)] + [(f"Tier {n}", n) for n in range(1, 9)])
        self.enchantment = self._select("Enchantement", [("Tous les enchantements", None)] + [(f"Enchantement .{n}", n) for n in range(5)])
        self.quality = self._select("Qualité", [("Toutes les qualités", None)] + [(f"{n} · {label}", n) for n, label in enumerate(QUALITIES, 1)])
        for column, widget in enumerate((self.category_button, self.tier, self.enchantment, self.quality)):
            filters_layout.addWidget(widget, 1, column)
        layout.addWidget(filters)

        self.search_delay = QTimer(self)
        self.search_delay.setSingleShot(True)
        self.search_delay.setInterval(140)
        self.search_delay.timeout.connect(self._refresh)
        self.search.textChanged.connect(lambda _: self.search_delay.start())

        body = QHBoxLayout()
        body.setSpacing(12)
        self.table = QTableView()
        self.table.setObjectName("itemsTable")
        self.table.setModel(self.model)
        self.table.setItemDelegateForColumn(0, NeutralIconDelegate(self.table))
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setIconSize(QSize(43, 43))
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(52)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column, width in enumerate((0, 60, 84, 85, 126)):
            if column:
                self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
                self.table.setColumnWidth(column, width)
        self.table.selectionModel().currentRowChanged.connect(self._show_selected)
        body.addWidget(self.table, 1)

        detail = QFrame()
        detail.setObjectName("itemDetail")
        detail.setFixedWidth(235)
        detail_col = QVBoxLayout(detail)
        detail_col.setContentsMargins(17, 21, 17, 17)
        detail_col.setSpacing(12)
        detail_title = QLabel("FICHE D'OBJET")
        detail_title.setObjectName("detailCaption")
        detail_col.addWidget(detail_title)
        self.detail_icon = QLabel()
        self.detail_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_icon.setMinimumHeight(106)
        detail_col.addWidget(self.detail_icon)
        self.detail_name = QLabel("Sélectionne un objet")
        self.detail_name.setWordWrap(True)
        self.detail_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_name.setObjectName("detailName")
        detail_col.addWidget(self.detail_name)
        self.detail_data = QLabel("")
        self.detail_data.setWordWrap(True)
        self.detail_data.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detail_data.setObjectName("detailData")
        detail_col.addWidget(self.detail_data)
        detail_col.addStretch()
        self.image_info = QLabel("Images intégrées au logiciel\nCatalogue utilisable hors ligne")
        self.image_info.setObjectName("offlineNote")
        self.image_info.setWordWrap(True)
        detail_col.addWidget(self.image_info)
        body.addWidget(detail)
        layout.addLayout(body, 1)

    def _refresh(self, *_):
        items = self.catalogue.find(
            self.search.text(),
            market_path=self.market_path,
            tier=self.tier.currentData(),
            enchantment=self.enchantment.currentData(),
            quality=self.quality.currentData(),
        )
        self.model.update(items, self.quality.currentData())
        self.counter.setText(f"{len(items):,} / {len(self.catalogue.items):,} objets".replace(",", " "))
        if items:
            self.table.selectRow(0)
        else:
            self.detail_icon.clear()
            self.detail_name.setText("Aucun objet trouvé")
            self.detail_data.clear()

    def _show_selected(self, current: QModelIndex, previous: QModelIndex):
        if not current.isValid() or current.row() >= len(self.model.items):
            return
        item = self.model.items[current.row()]
        quality = self.quality.currentData() if item.has_qualities else None
        self.detail_icon.setPixmap(self.icons.icon(item.item_id, quality or 1).pixmap(
            96, 96, QIcon.Mode.Normal))
        self.detail_name.setText(item.name)
        self.detail_data.setText(
            f"ID : {item.item_id}\n\n"
            f"Catégorie : {item.market_path[0]}\n"
            f"Type : {item.market_path[1]}\n"
            f"Famille : {item.market_path[2]}\n"
            f"Tier : {'T' + str(item.tier) if item.tier else '—'}\n"
            f"Enchantement : .{item.enchantment}\n"
            f"Qualité : {QUALITIES[quality-1] if quality else ('1 à 5' if item.has_qualities else '—')}"
        )

    def closeEvent(self, event):
        self.icons.close()
        super().closeEvent(event)
