"""Optional interface click, played in order without blocking the Qt UI.

Windows' asynchronous PlaySound replaces a sound already playing. A short
click can therefore be clipped by the next click. Queue short synchronous
plays on one daemon worker instead, and never delay the GUI event handler.
"""

from pathlib import Path
from queue import Empty, Full, Queue
import sys
import threading


CLICK_WAV = Path(__file__).resolve().parent / "assets" / "ui_click.wav"


class ClickSound:
    def __init__(self, enabled: bool = True, path: Path = CLICK_WAV):
        self.enabled = enabled
        self.path = Path(path)
        self._queue = Queue(maxsize=8)
        self._worker = None
        self._worker_lock = threading.Lock()

    def play(self):
        if not self.enabled or sys.platform != "win32" or not self.path.is_file():
            return
        with self._worker_lock:
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(
                    target=self._play_queued, name="SamiClickSound", daemon=True
                )
                self._worker.start()
            try:
                self._queue.put_nowait(True)
            except Full:
                # Keep rapid accidental multi-clicks from producing a long echo.
                pass

    def _play_queued(self):
        try:
            import winsound
        except ImportError:
            return
        while True:
            try:
                self._queue.get(timeout=2.0)
            except Empty:
                # A short-lived worker avoids lingering threads after windows close.
                with self._worker_lock:
                    if self._queue.empty():
                        self._worker = None
                        return
                continue
            try:
                if self.enabled:
                    winsound.PlaySound(
                        str(self.path),
                        winsound.SND_FILENAME | winsound.SND_NODEFAULT,
                    )
            except (OSError, RuntimeError):
                # Audio failures must never interrupt user interaction.
                pass
            finally:
                self._queue.task_done()
