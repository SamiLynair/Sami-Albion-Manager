"""Non-blocking Qt interface for checking and applying GitHub releases."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import QMessageBox, QProgressDialog

from .updater import (
    Release, UpdateError, check_latest_release, download_release, start_windows_install,
)


class _CheckWorker(QThread):
    checked = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            self.checked.emit(check_latest_release())
        except Exception as exc:
            self.failed.emit(str(exc))


class _DownloadWorker(QThread):
    progress = Signal(int)
    downloaded = Signal(object)
    failed = Signal(str)

    def __init__(self, release: Release):
        super().__init__()
        self.release = release

    def run(self):
        try:
            result = download_release(
                self.release,
                report_progress=lambda n, total: self.progress.emit(min(100, n * 100 // total)),
                is_cancelled=self.isInterruptionRequested,
            )
            self.downloaded.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class UpdateController(QObject):
    def __init__(self, window, button):
        super().__init__(window)
        self.window = window
        self.button = button
        self.checker: _CheckWorker | None = None
        self.downloader: _DownloadWorker | None = None
        self.progress_dialog: QProgressDialog | None = None
        self._silent_check = True
        self._active_release: Release | None = None
        self._pending_file = None
        self._download_error = None
        button.clicked.connect(lambda: self.check_updates(silent=False))
        if getattr(sys, "frozen", False) and not os.getenv("SAMI_DISABLE_UPDATE_CHECK"):
            QTimer.singleShot(2200, lambda: self.check_updates(silent=True)
                              if self.window.isVisible() else None)

    def stop_workers(self) -> bool:
        """Prevent QThread destruction while a network operation is running."""
        for worker in (self.checker, self.downloader):
            if worker is not None and worker.isRunning():
                worker.requestInterruption()
                if not worker.wait(25_000):
                    return False
        return True

    def check_updates(self, *, silent: bool):
        if self.checker is not None or self.downloader is not None:
            return
        self._silent_check = silent
        self.button.setEnabled(False)
        self.button.setText("↻   Recherche en cours…")
        worker = _CheckWorker(self)
        self.checker = worker
        worker.checked.connect(self._on_checked)
        worker.failed.connect(self._on_check_error)
        worker.finished.connect(self._on_check_finished)
        worker.start()

    def _on_check_finished(self):
        worker = self.checker
        self.checker = None
        if worker is not None:
            worker.deleteLater()
        self.button.setEnabled(True)
        self.button.setText("↻   Mises à jour")

    def _on_check_error(self, message: str):
        if not self._silent_check:
            QMessageBox.warning(self.window, "Mises à jour", message)

    def _on_checked(self, release: Release | None):
        if release is None:
            if not self._silent_check:
                QMessageBox.information(self.window, "Mises à jour",
                                        "Tu utilises déjà la dernière version disponible.")
            return
        if not getattr(sys, "frozen", False):
            if not self._silent_check:
                QMessageBox.information(
                    self.window, "Mise à jour disponible",
                    f"Version {release.version} disponible sur GitHub.\n"
                    "L'installation automatique fonctionne dans le programme Windows compilé.",
                )
            return
        notes = release.notes.strip()
        excerpt = (notes[:650] + "…") if len(notes) > 650 else notes
        description = f"Une nouvelle version ({release.version}) est disponible.\n\n"
        if excerpt:
            description += f"{excerpt}\n\n"
        description += "Télécharger et installer maintenant ?\nLe logiciel redémarrera."
        answer = QMessageBox.question(
            self.window, "Nouvelle mise à jour", description,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._download(release)

    def _download(self, release: Release):
        self._active_release = release
        self._pending_file = None
        self._download_error = None
        self.progress_dialog = QProgressDialog(
            f"Téléchargement de la version {release.version}…", "Annuler", 0, 100, self.window
        )
        self.progress_dialog.setWindowTitle("Mise à jour de Sami Albion Manager")
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.setValue(0)
        worker = _DownloadWorker(release)
        self.downloader = worker
        self.button.setEnabled(False)
        worker.progress.connect(self.progress_dialog.setValue)
        worker.downloaded.connect(self._download_succeeded)
        worker.failed.connect(self._download_failed)
        worker.finished.connect(self._download_finished)
        self.progress_dialog.canceled.connect(worker.requestInterruption)
        worker.start()

    def _download_succeeded(self, path):
        self._pending_file = path

    def _download_failed(self, message):
        self._download_error = message

    def _download_finished(self):
        worker = self.downloader
        self.downloader = None
        if worker is not None:
            worker.deleteLater()
        if self.progress_dialog is not None:
            self.progress_dialog.close()
            self.progress_dialog.deleteLater()
            self.progress_dialog = None
        self.button.setEnabled(True)
        if self._download_error:
            QMessageBox.warning(self.window, "Mise à jour interrompue", self._download_error)
            return
        if self._pending_file is None or self._active_release is None:
            return
        try:
            start_windows_install(self._pending_file, self._active_release)
        except (UpdateError, OSError) as exc:
            QMessageBox.critical(self.window, "Installation impossible", str(exc))
            return
        self.window.close()
        from PySide6.QtWidgets import QApplication
        QApplication.instance().quit()
