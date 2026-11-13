"""Gathering page backed by local demonstration sessions only.

There is intentionally no network, packet capture, memory reading or game
process access. A future approved event source can feed GatheringStore without
changing this page's accounting logic.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt, QTimer, QSize
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from .gathering_sessions import GatheringStore
from .inventory_catalog import OfflineItemCatalog
from .item_icons import OfflineIconStore


def _demo_database_path() -> Path:
    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    directory = Path(base) if base else Path.home() / ".sami_albion_manager"
    return directory / "gathering_demo.sqlite3"


def _number(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _duration(seconds: float) -> str:
    elapsed = max(0, int(seconds))
    hours, remaining = divmod(elapsed, 3600)
    minutes, seconds = divmod(remaining, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


class GatheringPage(QWidget):
    """Review persisted gathering events and explicitly generate demo events."""

    DEMO_EVENTS = (
        ("T6_ORE", 3, 1, 1),
        ("T7_FIBER", 4, 0, 1),
        ("T5_HIDE", 2, 1, 0),
        ("T6_WOOD", 5, 0, 2),
    )

    def __init__(self, parent=None, *, database_path: str | Path | None = None):
        super().__init__(parent)
        # Keep demo data strictly separate from future real/approved sources.
        self.store = GatheringStore(database_path or _demo_database_path())
        self.catalog = OfflineItemCatalog()
        self.icons = OfflineIconStore()
        self._closed = False
        self._build()
        self._load_sessions()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._show_summary)
        self._refresh_timer.start(5000)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        title = QLabel("RÉCOLTE")
        title.setObjectName("catalogueTitle")
        root.addWidget(title)

        caution = QLabel(
            "MODE DÉMONSTRATION  •  événements fictifs, aucune donnée lue dans Albion Online"
        )
        caution.setObjectName("gatheringCaution")
        caution.setWordWrap(True)
        root.addWidget(caution)

        controls = QFrame()
        controls.setObjectName("gatheringControls")
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(14, 12, 14, 12)
        controls_layout.setSpacing(8)

        first_row = QHBoxLayout()
        self.character_input = QLineEdit()
        self.character_input.setObjectName("gatheringCharacter")
        self.character_input.setPlaceholderText("Nom du personnage (ex. Sami)")
        self.character_input.setAccessibleName("Personnage de la session de démonstration")
        first_row.addWidget(self.character_input, 1)
        self.start_button = QPushButton("Démarrer une session")
        self.start_button.setObjectName("gatheringAction")
        self.start_button.clicked.connect(self._start_session)
        first_row.addWidget(self.start_button)
        controls_layout.addLayout(first_row)

        second_row = QHBoxLayout()
        self.session_picker = QComboBox()
        self.session_picker.setObjectName("gatheringSession")
        self.session_picker.setAccessibleName("Sessions de récolte enregistrées")
        self.session_picker.currentIndexChanged.connect(self._show_summary)
        second_row.addWidget(self.session_picker, 1)

        self.simulate_button = QPushButton("+ Simuler une récolte")
        self.simulate_button.setObjectName("gatheringAction")
        self.simulate_button.clicked.connect(self._simulate_event)
        second_row.addWidget(self.simulate_button)

        self.end_button = QPushButton("Terminer la session")
        self.end_button.setObjectName("gatheringAction")
        self.end_button.clicked.connect(self._end_session)
        second_row.addWidget(self.end_button)
        controls_layout.addLayout(second_row)

        self.message = QLabel("")
        self.message.setObjectName("gatheringMessage")
        self.message.setWordWrap(True)
        controls_layout.addWidget(self.message)
        root.addWidget(controls)

        metrics = QGridLayout()
        metrics.setSpacing(9)
        self.total_value = self._metric(metrics, 0, 0, "RESSOURCES RÉCOLTÉES")
        self.event_value = self._metric(metrics, 0, 1, "ACTIONS DE RÉCOLTE")
        self.duration_value = self._metric(metrics, 0, 2, "DURÉE")
        self.rate_value = self._metric(metrics, 0, 3, "RESSOURCES / HEURE")
        root.addLayout(metrics)

        details_heading = QLabel("DÉTAIL DES RESSOURCES")
        details_heading.setObjectName("detailCaption")
        root.addWidget(details_heading)

        self.table = QTableWidget(0, 5)
        self.table.setObjectName("gatheringTable")
        self.table.setHorizontalHeaderLabels(
            ("Ressource", "Normal", "Bonus", "Premium", "Total")
        )
        self.table.setIconSize(QSize(38, 38))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(48)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 5):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setMinimumHeight(160)
        root.addWidget(self.table, 1)

        disclaimer = QLabel(
            "Estimation en argent indisponible : aucun prix de marché n'est "
            "récupéré automatiquement. Les simulations restent dans une base "
            "locale distincte de tes futures véritables sessions."
        )
        disclaimer.setObjectName("catalogueSubtitle")
        disclaimer.setWordWrap(True)
        root.addWidget(disclaimer)

    @staticmethod
    def _metric(layout: QGridLayout, row: int, column: int, caption: str) -> QLabel:
        panel = QFrame()
        panel.setObjectName("craftMetric")
        col = QVBoxLayout(panel)
        col.setContentsMargins(9, 8, 9, 8)
        col.setSpacing(3)
        title = QLabel(caption)
        title.setObjectName("craftMetricCaption")
        title.setWordWrap(True)
        value = QLabel("0")
        value.setObjectName("craftMetricValue")
        col.addWidget(title)
        col.addWidget(value)
        layout.addWidget(panel, row, column)
        return value

    def _load_sessions(self, selected_id: str | None = None):
        selected_id = selected_id or self.session_picker.currentData()
        sessions = self.store.list_sessions()
        self.session_picker.blockSignals(True)
        self.session_picker.clear()
        for session_id, character, started_at, ended_at in sessions:
            date = datetime.fromisoformat(started_at).strftime("%d/%m/%Y %H:%M")
            status = "terminée" if ended_at else "en cours"
            self.session_picker.addItem(f"{character} • {date} • {status}", session_id)
        index = self.session_picker.findData(selected_id)
        if index >= 0:
            self.session_picker.setCurrentIndex(index)
        self.session_picker.blockSignals(False)
        self._show_summary()

    def _start_session(self):
        name = self.character_input.text().strip()
        if not name:
            self.message.setText("Renseigne d'abord le nom du personnage.")
            return
        if any(ended is None for _, _, _, ended in self.store.list_sessions()):
            self.message.setText("Termine la session en cours avant d'en démarrer une autre.")
            return
        session_id = self.store.start_session(name)
        self.message.setText(f"Session fictive commencée pour {name}.")
        self._load_sessions(session_id)

    def _end_session(self):
        session_id = self.session_picker.currentData()
        if session_id is None:
            return
        self.store.end_session(session_id)
        self.message.setText("Session de démonstration terminée et conservée.")
        self._load_sessions(session_id)

    def _simulate_event(self):
        session_id = self.session_picker.currentData()
        if session_id is None:
            return
        current = self.store.summary(session_id)
        item_id, normal, bonus, premium = self.DEMO_EVENTS[
            current.event_count % len(self.DEMO_EVENTS)
        ]
        self.store.add_event(
            session_id, item_id, normal,
            gathering_bonus=bonus, premium_bonus=premium,
        )
        name = self.catalog.by_id.get(item_id)
        self.message.setText(
            f"Événement fictif : +{normal + bonus + premium} "
            f"{name.name if name else item_id}."
        )
        self._show_summary()

    def _show_summary(self, *_):
        session_id = self.session_picker.currentData()
        self.table.setRowCount(0)
        if session_id is None:
            self.total_value.setText("0")
            self.event_value.setText("0")
            self.duration_value.setText("00:00:00")
            self.rate_value.setText("0")
            self.start_button.setEnabled(True)
            self.end_button.setEnabled(False)
            self.simulate_button.setEnabled(False)
            return

        summary = self.store.summary(session_id)
        self.total_value.setText(_number(summary.total_resources))
        self.event_value.setText(_number(summary.event_count))
        self.duration_value.setText(_duration(summary.duration_seconds))
        self.rate_value.setText(_number(round(summary.resources_per_hour)))

        active = summary.ended_at is None
        self.start_button.setEnabled(
            not any(ended is None for _, _, _, ended in self.store.list_sessions())
        )
        self.end_button.setEnabled(active)
        self.simulate_button.setEnabled(active)

        self.table.setRowCount(len(summary.resources))
        for row, resource in enumerate(summary.resources):
            catalog_item = self.catalog.by_id.get(resource.item_id)
            label = catalog_item.name if catalog_item else resource.item_id
            name_cell = QTableWidgetItem(label)
            name_cell.setIcon(self.icons.icon(resource.item_id))
            name_cell.setToolTip(resource.item_id)
            self.table.setItem(row, 0, name_cell)
            for column, count in enumerate(
                (resource.standard, resource.gathering_bonus,
                 resource.premium_bonus, resource.total), start=1
            ):
                number_cell = QTableWidgetItem(_number(count))
                number_cell.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
                )
                self.table.setItem(row, column, number_cell)

    def closeEvent(self, event):
        if not self._closed:
            self._closed = True
            self._refresh_timer.stop()
            self.icons.close()
            self.store.close()
        super().closeEvent(event)
