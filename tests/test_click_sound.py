"""UI click sound should be tiny, valid and entirely optional."""

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
