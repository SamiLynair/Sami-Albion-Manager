"""Offline tests for Windows Socket framing and resource index resolution."""

import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from samialbion.item_index_map import find_index_file, load_index_file
from samialbion.photon_gathering import PhotonGatheringDecoder
from samialbion.windows_raw_capture import udp_payload_from_ipv4


def wrap_ipv4(payload: bytes, port: int = 5056, *, fragment: bool = False) -> bytes:
    udp_length = 8 + len(payload)
    header = bytearray(20)
    header[0] = 0x45
    header[2:4] = struct.pack(">H", 20 + udp_length)
    header[6:8] = struct.pack(">H", 0x2000 if fragment else 0)
    header[8] = 64
    header[9] = 17
    header[12:16] = bytes([34, 1, 2, 3])
    header[16:20] = bytes([192, 168, 1, 22])
    return bytes(header) + struct.pack(">HHHH", port, 60321, udp_length, 0) + payload


def join_response():
    name = b"ExampleUser"
    params = (
        b"\x03" +  # 3 values
        b"\x00\x09\xd2\x09" +  # user id 617 (zigzag)
        b"\x02\x07" + bytes([len(name)]) + name +
        b"\xfd\x0b\x02"  # op id 2
    )
    body = b"\xf3\x03" + b"\x00" + b"\x00\x00" + b"\x08" + params
    command = b"\x06\x00\x00\x00" + struct.pack(">II", len(body) + 12, 99) + body
    return struct.pack(">HBBII", 0xF101, 0, 1, 100, 200) + command


class SocketComponentsTests(unittest.TestCase):
    def test_ipv4_valid_udp_payload_and_source(self):
        payload = b"\xf1\x00\x01\x02"
        self.assertEqual(
            udp_payload_from_ipv4(wrap_ipv4(payload)),
            ("34.1.2.3", 5056, 60321, payload),
        )

    def test_ipv4_fragments_and_invalid_lengths_rejected(self):
        self.assertIsNone(udp_payload_from_ipv4(wrap_ipv4(b"123", fragment=True)))
        frame = bytearray(wrap_ipv4(b"123"))
        frame[2:4] = b"\x00\x02"
        self.assertIsNone(udp_payload_from_ipv4(bytes(frame)))
        frame = bytearray(wrap_ipv4(b"123"))
        frame[9] = 6  # TCP, not UDP
        self.assertIsNone(udp_payload_from_ipv4(bytes(frame)))

    def test_join_response_extracts_own_character(self):
        people, harvest = PhotonGatheringDecoder().decode_with_identity(join_response())
        self.assertEqual(len(people), 1)
        self.assertEqual(people[0].character, "ExampleUser")
        self.assertEqual(people[0].user_object_id, 617)
        self.assertEqual(harvest, [])

    def test_indexed_items_file_makes_network_id_readable(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "IndexedItems.json"
            path.write_text(json.dumps([
                {"Index": 630, "UniqueName": "T6_ORE"},
                {"Index": 17, "UniqueName": "T4_FIBER"},
                {"Index": "bogus", "UniqueName": ""},
            ]), encoding="utf-8")
            self.assertEqual(load_index_file(path), {630: "T6_ORE", 17: "T4_FIBER"})

    def test_find_reference_under_local_appdata(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "StatisticsAnalysisTool" / "Instances" / "abc" / "GameFiles" / "IndexedItems.json"
            path.parent.mkdir(parents=True)
            path.write_text("[]", encoding="utf-8")
            with patch.dict("os.environ", {"LOCALAPPDATA": folder}):
                self.assertEqual(find_index_file(), path)


if __name__ == "__main__":
    unittest.main()
