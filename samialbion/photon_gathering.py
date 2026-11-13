"""Minimal, bounded Photon UDP/Protocol18 harvesting-event decoder.

This is a fresh Python implementation of the protocol's public wire format.
It only accepts events with Albion's HarvestFinished code (61) and does not
retain unrelated events, packet contents or character details.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct


MAX_PACKET = 65535
MAX_COLLECTION = 65535
MAX_DEPTH = 12
HARVEST_FINISHED = 61


class DecodeError(ValueError):
    """Truncated, unsupported, or malformed Photon data."""


@dataclass(frozen=True, slots=True)
class HarvestEvent:
    user_object_id: int
    object_id: int
    item_index: int
    standard: int
    gathering_bonus: int
    premium_bonus: int
    event_id: str

    @property
    def total(self) -> int:
        return self.standard + self.gathering_bonus + self.premium_bonus


class _Reader:
    def __init__(self, data: bytes):
        self.data = memoryview(data)
        self.pos = 0

    def read(self, n: int) -> bytes:
        if n < 0 or n > len(self.data) - self.pos:
            raise DecodeError("Truncated Photon payload")
        result = bytes(self.data[self.pos:self.pos + n])
        self.pos += n
        return result

    def byte(self) -> int:
        return self.read(1)[0]

    def varuint(self, *, limit_bits: int = 64) -> int:
        result = 0
        for shift in range(0, limit_bits, 7):
            octet = self.byte()
            result |= (octet & 0x7f) << shift
            if octet < 128:
                if result >= 1 << limit_bits:
                    raise DecodeError("Varint exceeds integer limit")
                return result
        raise DecodeError("Varint too long")

    def zigzag(self, bits: int) -> int:
        unsigned = self.varuint(limit_bits=bits)
        return (unsigned >> 1) ^ -(unsigned & 1)

    def count(self) -> int:
        value = self.varuint(limit_bits=32)
        if value > MAX_COLLECTION:
            raise DecodeError("Excessively large collection")
        return value

    def value(self, kind: int | None = None, *, depth: int = 0):
        if depth > MAX_DEPTH:
            raise DecodeError("Too many nested Photon objects")
        if kind is None:
            kind = self.byte()
        if kind == 2:
            return self.byte() != 0
        if kind == 3:
            return self.byte()
        if kind == 4:
            return int.from_bytes(self.read(2), "little", signed=True)
        if kind == 5:
            return struct.unpack("<f", self.read(4))[0]
        if kind == 6:
            return struct.unpack("<d", self.read(8))[0]
        if kind == 7:
            return self.read(self.count()).decode("utf-8")
        if kind == 8:
            return None
        if kind == 9:
            return self.zigzag(32)
        if kind == 10:
            return self.zigzag(64)
        if kind in (11, 15):
            return self.byte()
        if kind in (12, 16):
            return -self.byte()
        if kind in (13, 17):
            return int.from_bytes(self.read(2), "little")
        if kind in (14, 18):
            return -int.from_bytes(self.read(2), "little")
        if kind in (27, 28):
            return kind == 28
        if 29 <= kind <= 34:
            return 0
        if kind == 23:
            return [self.value(depth=depth + 1) for _ in range(self.count())]
        if kind == 21:  # Hashtable with dynamic key/value types
            n = self.count()
            return {self.value(depth=depth + 1): self.value(depth=depth + 1)
                    for _ in range(n)}
        if kind == 20:  # Typed dictionary, used for some Albion messages
            key_type, val_type = self.byte(), self.byte()
            if 20 in (key_type, val_type) or 64 in (key_type, val_type):
                raise DecodeError("Nested typed dictionary requires further support")
            return {
                self.value(None if key_type == 0 else key_type, depth=depth + 1):
                self.value(None if val_type == 0 else val_type, depth=depth + 1)
                for _ in range(self.count())
            }
        if kind == 67:
            return self.read(self.count())
        if kind in (68, 73, 74, 71, 66):
            n = self.count()
            if kind == 68:
                return [int.from_bytes(self.read(2), "little", signed=True) for _ in range(n)]
            if kind == 73:
                return [self.zigzag(32) for _ in range(n)]
            if kind == 74:
                return [self.zigzag(64) for _ in range(n)]
            if kind == 71:
                return [self.value(7, depth=depth + 1) for _ in range(n)]
            packed = self.read((n + 7) // 8)
            return [bool(packed[i // 8] & (1 << (i % 8))) for i in range(n)]
        if kind == 19 or 128 <= kind <= 228:
            subtype = self.byte() if kind == 19 else kind - 128
            return (subtype, self.read(self.count()))
        raise DecodeError(f"Photon type {kind} not implemented")

    def parameters(self) -> dict[int, object]:
        count = self.byte()
        return {self.byte(): self.value() for _ in range(count)}


def _nonnegative_integer(parameters: dict[int, object], index: int) -> int:
    value = parameters.get(index, 0)
    if type(value) is not int or value < 0:
        raise DecodeError(f"Invalid harvest field {index}")
    return value


class PhotonGatheringDecoder:
    """Decode HarvestFinished from a Photon/Protocol18 UDP payload.

    Commands 6 (reliable) and 7 (unreliable) are supported. Fragmented Photon
    commands are deliberately skipped until reassembly support is implemented.
    """

    def decode(self, payload: bytes, *, source: str = "") -> list[HarvestEvent]:
        if not 12 <= len(payload) <= MAX_PACKET:
            return []
        harvests: list[HarvestEvent] = []
        offset = 0
        # A single UDP datagram may contain multiple Photon packets.
        while offset + 12 <= len(payload):
            start = offset
            flags = payload[start + 2]
            count = payload[start + 3]
            if flags == 1:  # Encrypted payload
                return harvests
            if count > 128:
                return harvests
            peer = int.from_bytes(payload[start:start + 2], "big")
            challenge = int.from_bytes(payload[start + 8:start + 12], "big")
            offset = start + 12 + (4 if flags == 0xcc else 0)
            if offset > len(payload):
                break
            for _ in range(count):
                if offset + 12 > len(payload):
                    return harvests
                command_start = offset
                kind = payload[offset]
                channel = payload[offset + 1]
                command_length = int.from_bytes(payload[offset + 4:offset + 8], "big")
                sequence = int.from_bytes(payload[offset + 8:offset + 12], "big")
                if command_length < 12 or command_start + command_length > len(payload):
                    return harvests
                command = payload[command_start + 12: command_start + command_length]
                offset += command_length
                if kind == 7:  # SendUnreliable adds four bytes
                    if len(command) < 4:
                        continue
                    command = command[4:]
                elif kind != 6:
                    continue
                if len(command) < 2 or command[1] != 4:  # Photon Event
                    continue
                try:
                    reader = _Reader(command[2:])
                    reader.byte()  # Photon event byte; Albion code is param 252
                    params = reader.parameters()
                    if params.get(252) != HARVEST_FINISHED:
                        continue
                    amounts = tuple(_nonnegative_integer(params, k) for k in (5, 6, 7))
                    if not sum(amounts):
                        continue
                    uid = _nonnegative_integer(params, 0)
                    object_id = _nonnegative_integer(params, 3)
                    item_index = _nonnegative_integer(params, 4)
                    if not uid or not item_index:
                        continue
                    # A reliable command's sequence number is reused across
                    # retransmissions, giving stable deduplication identifiers.
                    event_id = f"{source}|{peer}|{challenge}|{channel}|{sequence}"
                    harvests.append(HarvestEvent(
                        uid, object_id, item_index, *amounts, event_id,
                    ))
                except (DecodeError, UnicodeError, TypeError, ValueError):
                    continue
            if offset <= start:
                break
        return harvests
