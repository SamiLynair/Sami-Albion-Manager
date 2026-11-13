"""Protocol18 harvest decoder tests using independently encoded fixtures."""

import struct
import unittest

from samialbion.photon_gathering import (
    PhotonGatheringDecoder, DecodeError, _Reader, HARVEST_FINISHED,
)


def varint(n):
    result = bytearray()
    while n >= 128:
        result.append((n & 127) | 128)
        n >>= 7
    result.append(n)
    return bytes(result)


def compressed_int(number):
    zz = (number << 1) ^ (number >> 63)
    return bytes([9]) + varint(zz)


def event_frame(*, code=HARVEST_FINISHED, uid=1234,
                idx=630, standard=3, bonus=2, premium=1,
                sequence=42, kind=6):
    params = {0: uid, 3: 112, 4: idx, 5: standard,
              6: bonus, 7: premium, 252: code}
    body = bytes([1, 4, 0, len(params)])
    for key, number in params.items():
        body += bytes([key]) + compressed_int(number)
    if kind == 7:
        body = struct.pack(">I", 5) + body
    command = bytes([kind, 0, 0, 0]) + struct.pack(">II", len(body) + 12, sequence) + body
    # 2 peer, 1 flags, 1 command count, 4 sent time, 4 challenge
    return struct.pack(">HBBII", 0xF101, 0, 1, 100, 200) + command


class PhotonGatheringTests(unittest.TestCase):
    def setUp(self):
        self.decoder = PhotonGatheringDecoder()

    def test_harvest_fields_decoded_from_photon_datagram(self):
        result = self.decoder.decode(event_frame(), source="server-A")
        self.assertEqual(len(result), 1)
        e = result[0]
        self.assertEqual((e.user_object_id, e.object_id, e.item_index), (1234, 112, 630))
        self.assertEqual((e.standard, e.gathering_bonus, e.premium_bonus), (3, 2, 1))
        self.assertEqual(e.total, 6)
        self.assertEqual(e.event_id, "server-A|61697|200|0|42")

    def test_unreliable_packet_and_multiple_commands(self):
        self.assertEqual(self.decoder.decode(event_frame(kind=7))[0].total, 6)
        single = event_frame()
        self.assertEqual(len(self.decoder.decode(single + single)), 2)

    def test_other_events_rejected(self):
        self.assertEqual(self.decoder.decode(event_frame(code=62)), [])
        self.assertEqual(self.decoder.decode(event_frame(uid=0)), [])
        self.assertEqual(self.decoder.decode(event_frame(standard=0, bonus=0, premium=0)), [])

    def test_packet_retransmission_gives_same_event_id(self):
        first = self.decoder.decode(event_frame())[0]
        second = self.decoder.decode(event_frame())[0]
        self.assertEqual(first.event_id, second.event_id)
        changed = self.decoder.decode(event_frame(sequence=43))[0]
        self.assertNotEqual(first.event_id, changed.event_id)

    def test_truncation_and_unrecognized_types_are_safe(self):
        full = event_frame()
        self.assertEqual(self.decoder.decode(full[:21]), [])
        self.assertEqual(self.decoder.decode(b"bad"), [])
        reader = _Reader(b"\x09\x06")
        self.assertEqual(reader.value(), 3)
        with self.assertRaises(DecodeError):
            _Reader(b"\x09\x80").value()
        with self.assertRaises(DecodeError):
            _Reader(b"\x50").value()


if __name__ == "__main__":
    unittest.main()
