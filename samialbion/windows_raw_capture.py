"""Windows IPv4 raw-socket receiver for Photon UDP datagrams.

Opt-in diagnostic component. No outgoing traffic, packet recording,
process-memory access, injection or overlay.

On Windows, raw sockets need Administrator rights and an active IPv4 address.
The receiver only passes UDP application payloads to its callback.
"""

from __future__ import annotations

import ipaddress
import socket
import sys
import threading
from typing import Callable


KNOWN_PHOTON_PORTS = frozenset((5055, 5056, 5058))


def ipv4_addresses() -> list[str]:
    """Best-effort local addresses; no third-party dependency."""
    found = set()
    for name in (socket.gethostname(), socket.getfqdn()):
        try:
            found.update(info[4][0] for info in socket.getaddrinfo(
                name, None, socket.AF_INET, socket.SOCK_STREAM
            ) if info[4][0] and not info[4][0].startswith("127."))
        except OSError:
            continue
    return sorted(found)


def udp_payload_from_ipv4(packet: bytes) -> tuple[str, int, int, bytes] | None:
    """Validate an IPv4/UDP frame and remove its IP and UDP headers."""
    if len(packet) < 28 or packet[0] >> 4 != 4:
        return None
    ip_header = (packet[0] & 15) * 4
    if ip_header < 20 or len(packet) < ip_header + 8 or packet[9] != 17:
        return None
    # Skip IPv4 fragments; partial UDP messages cannot be decoded.
    frag = int.from_bytes(packet[6:8], "big")
    if frag & 0x3fff:
        return None
    ip_len = int.from_bytes(packet[2:4], "big")
    if ip_len < ip_header + 8 or ip_len > len(packet):
        return None
    header = packet[ip_header:ip_header + 8]
    src_port, dest_port, udp_len = (
        int.from_bytes(header[0:2], "big"),
        int.from_bytes(header[2:4], "big"),
        int.from_bytes(header[4:6], "big"),
    )
    if udp_len < 8 or udp_len > ip_len - ip_header:
        return None
    payload = packet[ip_header + 8:ip_header + udp_len]
    if not payload:
        return None
    if src_port not in KNOWN_PHOTON_PORTS and dest_port not in KNOWN_PHOTON_PORTS:
        if payload[0] not in (0xf1, 0xf2, 0xfe):
            return None
    return str(ipaddress.IPv4Address(packet[12:16])), src_port, dest_port, payload


class WindowsSocketCapture:
    """A minimal, stoppable raw IP receiver for explicitly selected address.

    callback(source_ip, src_port, dest_port, photon_bytes) runs on a background
    thread; it must not update Qt widgets directly.
    """

    def __init__(self, ipv4_address: str,
                 callback: Callable[[str, int, int, bytes], None]):
        self.address = str(ipaddress.IPv4Address(ipv4_address))
        self.callback = callback
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._sock: socket.socket | None = None

    def start(self) -> None:
        if sys.platform != "win32":
            raise OSError("Windows raw sockets are only supported on Windows")
        if self._thread is not None:
            raise RuntimeError("Capture already running")
        receiver = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
        try:
            receiver.bind((self.address, 0))
            receiver.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
            receiver.ioctl(socket.SIO_RCVALL, socket.RCVALL_ON)
            receiver.settimeout(0.5)
        except BaseException:
            receiver.close()
            raise
        self._sock = receiver
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="SamiPhotonReceive")
        self._thread.start()

    def _loop(self) -> None:
        sock = self._sock
        if sock is None:
            return
        while not self._stop.is_set():
            try:
                frame = sock.recv(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            parsed = udp_payload_from_ipv4(frame)
            if parsed is None:
                continue
            try:
                self.callback(*parsed)
            except Exception:
                # Consumer callbacks are isolated from the receiver loop.
                continue

    def stop(self) -> None:
        self._stop.set()
        sock = self._sock
        self._sock = None
        if sock is not None:
            try:
                sock.ioctl(socket.SIO_RCVALL, socket.RCVALL_OFF)
            except (OSError, AttributeError):
                pass
            sock.close()
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)
