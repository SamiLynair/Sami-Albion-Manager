"""Qt worker for Windows Socket tracking.

All native capture and decoding runs off the UI thread. Only explicitly
decoded player identity and HarvestFinished events cross the Qt signal bridge.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from .photon_gathering import PhotonGatheringDecoder
from .windows_raw_capture import WindowsSocketCapture


class PhotonSocketWorker(QThread):
    identity_seen = Signal(object)
    harvest_seen = Signal(object)
    capture_error = Signal(str)
    capture_ready = Signal()

    def __init__(self, ipv4: str, parent=None):
        super().__init__(parent)
        self.ipv4 = ipv4
        self._listener = None
        self._decoder = PhotonGatheringDecoder()

    def _on_udp(self, source: str, src_port: int, dest_port: int, payload: bytes):
        identities, harvests = self._decoder.decode_with_identity(payload, source=source)
        for character in identities:
            self.identity_seen.emit(character)
        for event in harvests:
            self.harvest_seen.emit(event)

    def run(self):
        self._listener = WindowsSocketCapture(self.ipv4, self._on_udp)
        try:
            self._listener.start()
            self.capture_ready.emit()
            while not self.isInterruptionRequested():
                self.msleep(200)
        except (OSError, ValueError, RuntimeError) as error:
            self.capture_error.emit(str(error))
        finally:
            self._listener.stop()
            self._listener = None

    def stop(self):
        self.requestInterruption()
        self.wait(2500)
