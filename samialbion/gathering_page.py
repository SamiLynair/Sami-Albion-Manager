"""Gathering sessions with demo, file-import and opt-in Socket beta modes."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import os

from PySide6.QtCore import QSettings, QStandardPaths, Qt, QTimer, QSize
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QPushButton, QFileDialog, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from .gathering_sessions import GatheringStore
from .inventory_catalog import OfflineItemCatalog
from .item_icons import OfflineIconStore
from .statistics_analysis_import import load_statistics_analysis_snapshot
from .item_index_map import find_index_file, load_index_file
from .socket_worker import PhotonSocketWorker
from .windows_raw_capture import ipv4_addresses


def _demo_database_path() -> Path:
    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    directory = Path(base) if base else Path.home() / ".sami_albion_manager"
    return directory / "gathering_demo.sqlite3"


def _find_statistics_analysis_file() -> str:
    """Locate Statistics Analysis snapshots only in its known local data tree."""
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return ""
    root = Path(local) / "StatisticsAnalysisTool"
    try:
        candidates = list(root.glob("Instances/*/UserData-EUROPE/Gathering.json"))
        candidates += list(root.glob("Instances/*/UserData/Gathering.json"))
        candidates += list(root.glob("Instances/*/UserData-AMERICA/Gathering.json"))
        candidates += list(root.glob("Instances/*/UserData-ASIA/Gathering.json"))
        candidates += list(root.glob("Default/UserData-EUROPE/Gathering.json"))
        return str(max(candidates, key=lambda p: p.stat().st_mtime_ns)) if candidates else ""
    except OSError:
        return ""


def _number(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _duration(seconds: float) -> str:
    elapsed = max(0, int(seconds))
    hours, remaining = divmod(elapsed, 3600)
    minutes, seconds = divmod(remaining, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


class GatheringPage(QWidget):
    """Review demo, Statistics Analysis snapshots or native Socket sessions."""

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
        live_path = Path(database_path).with_name("gathering_live.sqlite3") if database_path else _demo_database_path().with_name("gathering_live.sqlite3")
        self.live_store = GatheringStore(live_path)
        self._socket_worker = None
        self._active_live_session = None
        self._live_user_id = None
        self._item_indices = {}
        self.catalog = OfflineItemCatalog()
        self.icons = OfflineIconStore()
        self._closed = False
        self.preferences = QSettings("Sami", "SamiAlbionManager")
        self.sa_path = str(self.preferences.value("gathering/statistics_analysis_file", "") or "")
        if not self.sa_path:
            self.sa_path = _find_statistics_analysis_file()
        self._sa_sessions = {}
        self._sa_file_signature = None
        self._build()
        self._source_changed()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_clock)
        self._refresh_timer.start(5000)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        title = QLabel("RÉCOLTE")
        title.setObjectName("catalogueTitle")
        root.addWidget(title)

        self.caution = QLabel()
        self.caution.setObjectName("gatheringCaution")
        self.caution.setWordWrap(True)
        root.addWidget(self.caution)

        controls = QFrame()
        controls.setObjectName("gatheringControls")
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(14, 12, 14, 12)
        controls_layout.setSpacing(8)

        source_row = QHBoxLayout()
        self.source_mode = QComboBox()
        self.source_mode.setObjectName("gatheringSession")
        self.source_mode.addItem("Mode démonstration", "demo")
        self.source_mode.addItem("Statistics Analysis • fichier local", "sa")
        self.source_mode.addItem("Socket natif • bêta", "socket")
        source_row.addWidget(self.source_mode, 1)
        self.sa_pick_button = QPushButton("Choisir Gathering.json")
        self.sa_pick_button.setObjectName("gatheringAction")
        self.sa_pick_button.clicked.connect(self._choose_sa_file)
        source_row.addWidget(self.sa_pick_button)
        controls_layout.addLayout(source_row)

        self.socket_panel = QWidget()
        socket_controls = QHBoxLayout(self.socket_panel)
        socket_controls.setContentsMargins(0, 0, 0, 0)
        self.socket_interface = QComboBox()
        self.socket_interface.setObjectName("gatheringSession")
        for address in ipv4_addresses():
            self.socket_interface.addItem(address, address)
        self.socket_interface.setToolTip("Adresse IPv4 locale de l'interface réseau à surveiller")
        socket_controls.addWidget(self.socket_interface, 1)
        self.socket_button = QPushButton("Démarrer Socket")
        self.socket_button.setObjectName("gatheringAction")
        self.socket_button.clicked.connect(self._toggle_socket)
        socket_controls.addWidget(self.socket_button)
        self.index_button = QPushButton("IndexedItems.json")
        self.index_button.setObjectName("gatheringAction")
        self.index_button.clicked.connect(self._choose_index_file)
        socket_controls.addWidget(self.index_button)
        controls_layout.addWidget(self.socket_panel)

        self.sa_file_label = QLabel("")
        self.sa_file_label.setObjectName("gatheringMessage")
        self.sa_file_label.setWordWrap(True)
        controls_layout.addWidget(self.sa_file_label)

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
        saved_mode = self.preferences.value("gathering/source_mode", "demo")
        self.source_mode.setCurrentIndex(
            {"demo": 0, "sa": 1, "socket": 2}.get(saved_mode, 0)
        )
        self.source_mode.currentIndexChanged.connect(self._source_changed)

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

        self.disclaimer = QLabel()
        self.disclaimer.setObjectName("catalogueSubtitle")
        self.disclaimer.setWordWrap(True)
        root.addWidget(self.disclaimer)

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

    def _is_sa_mode(self) -> bool:
        return self.source_mode.currentData() == "sa"

    def _is_socket_mode(self) -> bool:
        return self.source_mode.currentData() == "socket"

    def _source_changed(self, *_):
        sa = self._is_sa_mode()
        native = self._is_socket_mode()
        if not native and self._socket_worker is not None:
            self._stop_socket()
        mode = "sa" if sa else ("socket" if native else "demo")
        self.preferences.setValue("gathering/source_mode", mode)
        self.character_input.setVisible(mode == "demo")
        self.start_button.setVisible(mode == "demo")
        self.simulate_button.setVisible(mode == "demo")
        self.end_button.setVisible(mode == "demo")
        self.socket_panel.setVisible(native)
        self.sa_pick_button.setVisible(sa)
        self.sa_file_label.setVisible(sa)
        self.caution.setText(
            "MODE SOCKET BÊTA • collecte directe, sans superposition au jeu"
            if native else
            ("STATISTICS ANALYSIS • lecture seule d'un fichier local"
             if sa else "MODE DÉMONSTRATION • événements fictifs")
        )
        self.disclaimer.setText(
            "Le fichier est lu sans modification. Actualisation après sauvegarde "
            "par Statistics Analysis, parfois après plusieurs récoltes. "
            "Durée et ressources/heure indisponibles depuis ce fichier."
            if sa else
            ("Socket Windows : lancer Sami en administrateur, puis se connecter "
             "à Albion pour identifier automatiquement le personnage. "
             "Index des objets importé depuis IndexedItems.json ; "
             "paquets fragmentés encore ignorés par cette bêta."
             if native else
             "Estimation en argent indisponible : aucun prix de marché n'est "
             "récupéré automatiquement. Les simulations restent dans une base "
             "locale distincte de tes futures véritables sessions.")
        )
        self.message.setText("")
        if sa:
            self._reload_sa(force=True)
        else:
            self._load_sessions()

    def _choose_index_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Table des objets d'Albion",
            str(find_index_file() or Path.home()), "IndexedItems.json (IndexedItems.json)"
        )
        if file_path:
            self.preferences.setValue("gathering/index_file", file_path)
            self._item_indices = {}
            self.message.setText("Table d'objets sélectionnée. Démarre Socket.")

    def _toggle_socket(self):
        if self._socket_worker is not None:
            self._stop_socket()
            return
        ip = self.socket_interface.currentData()
        if not ip:
            self.message.setText("Aucune adresse IPv4 trouvée. Vérifie ta connexion réseau.")
            return
        try:
            idx_path = str(self.preferences.value("gathering/index_file", "") or "")
            if not idx_path:
                indexed_file = find_index_file()
                idx_path = str(indexed_file) if indexed_file else ""
            if idx_path:
                self._item_indices = load_index_file(idx_path)
            else:
                self._item_indices = {}
        except (OSError, ValueError) as error:
            self.message.setText(f"Table des objets illisible : {error}")
            return
        if not self._item_indices:
            self.message.setText("IndexedItems.json introuvable. Choisis le fichier avec le bouton prévu.")
            return
        self._socket_worker = PhotonSocketWorker(ip, self)
        self._socket_worker.identity_seen.connect(self._on_socket_identity)
        self._socket_worker.harvest_seen.connect(self._on_socket_harvest)
        self._socket_worker.capture_error.connect(self._on_socket_error)
        self._socket_worker.capture_ready.connect(self._on_socket_ready)
        self._socket_worker.finished.connect(self._on_socket_finished)
        self.socket_button.setText("Arrêter Socket")
        self.socket_interface.setEnabled(False)
        self.message.setText("Démarrage Socket…")
        self._socket_worker.start()

    def _on_socket_ready(self):
        self.message.setText("Socket actif. Connecte ton personnage à Albion pour démarrer sa session.")

    def _on_socket_error(self, error: str):
        self.message.setText(f"Erreur Socket : {error}. Vérifie les droits administrateur et l'interface.")

    def _on_socket_finished(self):
        if self._socket_worker is not None:
            self._socket_worker.deleteLater()
            self._socket_worker = None
        if self._active_live_session is not None:
            try:
                self.live_store.end_session(self._active_live_session)
            except (ValueError, KeyError):
                pass
            self._active_live_session = None
        self._live_user_id = None
        self.socket_button.setText("Démarrer Socket")
        self.socket_interface.setEnabled(True)
        if self._is_socket_mode() and not self._closed:
            self._load_sessions()

    def _stop_socket(self):
        worker = self._socket_worker
        if worker is not None:
            worker.stop()
            self._socket_worker = None
            worker.deleteLater()
        if self._active_live_session is not None:
            self.live_store.end_session(self._active_live_session)
            self._active_live_session = None
        self._live_user_id = None
        self.socket_button.setText("Démarrer Socket")
        self.socket_interface.setEnabled(True)
        self.message.setText("Socket arrêté. Session locale enregistrée.")

    def _on_socket_identity(self, identity):
        if self._closed or self._socket_worker is None:
            return
        if self._live_user_id == identity.user_object_id and self._active_live_session:
            return
        if self._active_live_session is not None:
            self.live_store.end_session(self._active_live_session)
        self._live_user_id = identity.user_object_id
        self._active_live_session = self.live_store.start_session(identity.character)
        self.message.setText(f"Personnage détecté : {identity.character}. Récolte en direct active.")
        if self._is_socket_mode():
            self._load_sessions(self._active_live_session)

    def _on_socket_harvest(self, event):
        if self._closed or self._active_live_session is None:
            return
        if event.user_object_id != self._live_user_id:
            return
        item_id = self._item_indices.get(event.item_index, f"INDEX_{event.item_index}")
        try:
            added = self.live_store.add_event(
                self._active_live_session, item_id, event.standard,
                gathering_bonus=event.gathering_bonus,
                premium_bonus=event.premium_bonus, event_id=event.event_id,
            )
        except (ValueError, KeyError) as error:
            self.message.setText(f"Événement ignoré : {error}")
            return
        if added and self._is_socket_mode():
            self._load_sessions(self._active_live_session)

    def _choose_sa_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Fichier de récolte Statistics Analysis",
            self.sa_path or str(Path.home()), "Gathering.json (Gathering.json)"
        )
        if filename:
            self.sa_path = filename
            self.preferences.setValue("gathering/statistics_analysis_file", filename)
            self._sa_file_signature = None
            self._reload_sa(force=True)

    def _reload_sa(self, *, force: bool = False):
        if not self.sa_path:
            self.sa_file_label.setText("Sélectionne le Gathering.json créé par Statistics Analysis.")
            self._sa_sessions = {}
            self._load_sa_sessions()
            return
        path = Path(self.sa_path)
        self.sa_file_label.setText("Source : " + str(path))
        self.sa_file_label.setToolTip(str(path))
        try:
            stat = path.stat()
            signature = (stat.st_mtime_ns, stat.st_size)
            if not force and signature == self._sa_file_signature:
                return
            sessions = load_statistics_analysis_snapshot(path)
        except (OSError, ValueError, UnicodeError, TypeError) as error:
            self.message.setText(f"Lecture impossible : {error}")
            return
        except Exception as error:
            # Includes malformed JSON while a third-party app is saving.
            self.message.setText(f"Fichier temporairement illisible : {error}")
            return

        self._sa_file_signature = signature
        self._sa_sessions = {
            f"{entry.session_id}|{entry.character}": entry for entry in sessions
        }
        self.message.setText(
            f"{len(sessions)} session(s) lue(s) depuis le fichier de Statistics Analysis. "
            "Les modifications apparaissent après leur sauvegarde par SA."
        )
        self._load_sa_sessions()

    def _load_sa_sessions(self):
        selected = self.session_picker.currentData()
        self.session_picker.blockSignals(True)
        self.session_picker.clear()
        for key, entry in self._sa_sessions.items():
            date = entry.first_record_at.strftime("%d/%m/%Y %H:%M")
            self.session_picker.addItem(f"{entry.character} • {date} • SA", key)
        index = self.session_picker.findData(selected)
        if index >= 0:
            self.session_picker.setCurrentIndex(index)
        self.session_picker.blockSignals(False)
        self._show_summary()

    def _load_sessions(self, selected_id: str | None = None):
        selected_id = selected_id or self.session_picker.currentData()
        sessions = (self.live_store if self._is_socket_mode() else self.store).list_sessions()
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

    def _refresh_clock(self):
        """Poll the optional local file, or update demo duration."""
        if self._is_sa_mode():
            self._reload_sa()
            return
        session_id = self.session_picker.currentData()
        if session_id is None:
            return
        summary = (self.live_store if self._is_socket_mode() else self.store).summary(session_id)
        self.duration_value.setText(_duration(summary.duration_seconds))
        self.rate_value.setText(_number(round(summary.resources_per_hour)))

    def _show_summary(self, *_):
        session_id = self.session_picker.currentData()
        self.table.setRowCount(0)
        if self._is_sa_mode():
            self.start_button.setEnabled(False)
            self.end_button.setEnabled(False)
            self.simulate_button.setEnabled(False)
            entry = self._sa_sessions.get(session_id)
            self.total_value.setText(_number(entry.total_resources) if entry else "0")
            self.event_value.setText(_number(entry.event_count) if entry else "0")
            # Timestamps in SA's Gathering.json are per-resource record times;
            # the file does not supply a reliable session start/end duration.
            self.duration_value.setText("—")
            self.rate_value.setText("—")
            if entry:
                self._render_resources(entry.resources)
            return
        if session_id is None:
            self.total_value.setText("0")
            self.event_value.setText("0")
            self.duration_value.setText("00:00:00")
            self.rate_value.setText("0")
            self.start_button.setEnabled(True)
            self.end_button.setEnabled(False)
            self.simulate_button.setEnabled(False)
            return

        summary = (self.live_store if self._is_socket_mode() else self.store).summary(session_id)
        self.total_value.setText(_number(summary.total_resources))
        self.event_value.setText(_number(summary.event_count))
        self.duration_value.setText(_duration(summary.duration_seconds))
        self.rate_value.setText(_number(round(summary.resources_per_hour)))

        active = summary.ended_at is None
        self.start_button.setEnabled(
            not self._is_socket_mode() and
            not any(ended is None for _, _, _, ended in self.store.list_sessions())
        )
        self.end_button.setEnabled(active and not self._is_socket_mode())
        self.simulate_button.setEnabled(active and not self._is_socket_mode())

        self._render_resources(summary.resources)

    def _render_resources(self, resources):
        self.table.setRowCount(len(resources))
        for row, resource in enumerate(resources):
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
            if self._socket_worker is not None:
                self._stop_socket()
            self.icons.close()
            self.live_store.close()
            self.store.close()
        super().closeEvent(event)
