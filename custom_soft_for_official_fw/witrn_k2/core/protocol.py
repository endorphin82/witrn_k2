"""WITRN K2 64-byte protocol frame encoding, decoding, and checksum verification."""
from dataclasses import dataclass
import time

FRAME_SIZE = 64
PAYLOAD_SIZE = 52
MAGIC = b"\xff\x55"


class ProtocolError(RuntimeError):
    """Exception raised on protocol communication or checksum errors."""
    pass


@dataclass(frozen=True)
class Packet:
    command: int
    payload: bytes
    raw: bytes


def build_frame(command: int, payload: bytes = b"", *, reply: bool = True, tick: int = None) -> bytes:
    """Build a 64-byte command frame for WITRN K2.

    Args:
        command: Command ID (0-255).
        payload: Up to 52 bytes of payload.
        reply: Flag indicating expected reply.
        tick: Optional millisecond tick; if None, derived from monotonic time.
    """
    if not (0 <= command <= 255):
        raise ValueError("Command must be between 0 and 255")
    if len(payload) > PAYLOAD_SIZE:
        raise ValueError(f"Payload length cannot exceed {PAYLOAD_SIZE} bytes")

    tick = (int(time.monotonic() * 1000) if tick is None else tick) & 0xFFFFFFFF
    header = (
        0xFF,
        0x55,
        (tick // 1000) & 0xFF,
        (tick % 1000) & 0xFF,
        (((tick // 30) | 0x80) if reply else ((tick // 30) & 0x7F)) & 0xFF,
        (tick // 100) & 0xFF,
        (tick % 100) & 0xFF,
        (tick // 80) & 0xFF,
    )
    frame = bytearray(header)
    frame.extend(bytes((command, len(payload))) + payload.ljust(PAYLOAD_SIZE, b"\0"))
    # Inner checksum (bytes 8 to 61 inclusive)
    frame.append(sum(frame[8:62]) & 0xFF)
    # Outer checksum (bytes 0 to 61 inclusive)
    frame.append(sum(frame[:62]) & 0xFF)
    return bytes(frame)


def parse_frame(raw: bytes) -> Packet:
    """Parse and validate a 64-byte frame from WITRN K2."""
    if len(raw) != FRAME_SIZE:
        raise ProtocolError(f"Invalid HID frame size: {len(raw)}, expected {FRAME_SIZE}")
    if raw[:2] != MAGIC:
        raise ProtocolError(f"Invalid frame magic: {raw[:2].hex()}, expected ff55")
    payload_len = raw[9]
    if payload_len > PAYLOAD_SIZE:
        raise ProtocolError(f"Payload length exceeds {PAYLOAD_SIZE}: {payload_len}")

    inner_sum = sum(raw[8:62]) & 0xFF
    outer_sum = sum(raw[:62]) & 0xFF
    if raw[62] != inner_sum:
        raise ProtocolError(f"Inner checksum mismatch: got {hex(raw[62])}, expected {hex(inner_sum)}")
    if raw[63] != outer_sum:
        raise ProtocolError(f"Outer checksum mismatch: got {hex(raw[63])}, expected {hex(outer_sum)}")

    return Packet(raw[8], raw[10:10 + payload_len], bytes(raw))
