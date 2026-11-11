"""Tiny optional interface sound, played without blocking the Qt UI."""

from pathlib import Path
import sys
import time


CLICK_WAV = Path(__file__).resolve().parent / "assets" / "ui_click.wav"


class ClickSound:
    def __init__(self, enabled: bool = True, path: Path = CLICK_WAV):
        self.enabled = enabled
        self.path = path
        self._last_played = 0.0

    def play(self):
        if not self.enabled or sys.platform != "win32" or not self.path.is_file():
            return
        now = time.monotonic()
        if now - self._last_played < 0.035:
            return
        self._last_played = now
        try:
            import winsound
            winsound.PlaySound(
                str(self.path),
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )
        except (OSError, RuntimeError):
            # Missing audio devices must never stop the application.
            pass
