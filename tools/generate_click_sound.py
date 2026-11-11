"""Regenerate the short, filtered-noise UI click bundled in the app.

The reference interaction uses a 35 ms decaying noise burst, a high-pass
filter at 1.8 kHz, and a notch around 4 kHz. This file keeps the approximation
reproducible without depending on a downloaded copyrighted audio asset.
"""

import math
from pathlib import Path
import random
import struct
import wave

from scipy.signal import lfilter


RATE = 44_100
DURATION = 0.035
OUTPUT = Path(__file__).resolve().parents[1] / "samialbion/assets/ui_click.wav"


def biquad(kind: str, frequency: float, q: float):
    omega = 2 * math.pi * frequency / RATE
    cosine = math.cos(omega)
    alpha = math.sin(omega) / (2 * q)
    if kind == "highpass":
        b = [(1 + cosine) / 2, -(1 + cosine), (1 + cosine) / 2]
        a = [1 + alpha, -2 * cosine, 1 - alpha]
    else:
        b = [1, -2 * cosine, 1]
        a = [1 + alpha, -2 * cosine, 1 - alpha]
    return [v / a[0] for v in b], [v / a[0] for v in a]


def main():
    rng = random.Random(2157)
    count = int(RATE * DURATION)
    noise = [
        rng.uniform(-1, 1) * (1 - index / count) ** 8
        for index in range(count)
    ]
    for kind, frequency, q in (("highpass", 1800, 1), ("notch", 4000, 2)):
        b, a = biquad(kind, frequency, q)
        noise = lfilter(b, a, noise)

    samples = []
    for index, value in enumerate(noise):
        gain = .15 * (.001 / .15) ** (index / count)
        samples.append(max(-32768, min(32767, round(value * gain * 32767))))

    with wave.open(str(OUTPUT), "wb") as sound:
        sound.setnchannels(1)
        sound.setsampwidth(2)
        sound.setframerate(RATE)
        sound.writeframes(struct.pack(f"<{count}h", *samples))


if __name__ == "__main__":
    main()
