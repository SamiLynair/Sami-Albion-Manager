"""Unit tests for the short, non-blocking, sequenced interface click."""

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest
import wave

from samialbion.click_sound import CLICK_WAV, ClickSound


class ClickSoundTests(unittest.TestCase):
    def test_bundled_click_is_short_and_mono(self):
        with wave.open(str(CLICK_WAV), "rb") as sound:
            self.assertEqual(sound.getnchannels(), 1)
            self.assertLess(sound.getnframes() / sound.getframerate(), 0.06)

    def test_disabled_click_does_not_play(self):
        sound = ClickSound(enabled=False)
        sound.play()
        self.assertFalse(sound.enabled)

    def test_fast_clicks_play_in_sequence_without_interrupting(self):
        played = []
        all_played = Event()

        def record_play(path, flags):
            played.append((path, flags))
            if len(played) == 5:
                all_played.set()

        fake_winsound = SimpleNamespace(
            SND_FILENAME=0x20000,
            SND_NODEFAULT=0x0002,
            PlaySound=Mock(side_effect=record_play),
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "click.wav"
            path.write_bytes(b"test audio presence")
            sound = ClickSound(path=path)
            with (patch("samialbion.click_sound.sys.platform", "win32"),
                  patch.dict("sys.modules", {"winsound": fake_winsound})):
                for _ in range(5):
                    sound.play()
                self.assertTrue(all_played.wait(timeout=3), "Not every click was heard")
                self.assertEqual(len(played), 5)
                self.assertEqual(
                    played,
                    [(str(path), fake_winsound.SND_FILENAME | fake_winsound.SND_NODEFAULT)] * 5
                )
