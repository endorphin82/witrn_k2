"""WITRN K2 telemetry decoding and rate sampling."""
from dataclasses import asdict, dataclass
import math
import struct
from typing import Optional

from .protocol import FRAME_SIZE


@dataclass(frozen=True)
class Sample:
    time: float
    voltage: float
    current: float
    power: float
    signed_power: float
    resistance: Optional[float] = None
    temp_in: Optional[float] = None
    temp_out: Optional[float] = None
    dp: Optional[float] = None
    dn: Optional[float] = None
    ah: Optional[float] = None
    wh: Optional[float] = None
    record_seconds: Optional[int] = None
    uptime: Optional[int] = None
    group: Optional[int] = None
    segment: int = 0

    def dictionary(self) -> dict:
        return asdict(self)


def normalize_input(raw: bytes) -> bytes:
    """Normalize input frame: handle potential leading report ID (65 -> 64 bytes)."""
    raw = bytes(raw)
    if len(raw) == FRAME_SIZE:
        return raw
    if len(raw) == FRAME_SIZE + 1 and raw[0] == 0:
        return raw[1:]
    if not raw:
        return b""
    raise ValueError(f"Unexpected frame length: {len(raw)} bytes (expected {FRAME_SIZE})")


def dfu_checksum_matches(raw: bytes) -> bool:
    """Validate WITRN dual checksums."""
    data = normalize_input(raw)
    if len(data) != FRAME_SIZE:
        return False
    return (
        data[62] == (sum(data[8:62]) & 0xFF) and
        data[63] == (sum(data[:62]) & 0xFF)
    )


def decode_report(raw: bytes, elapsed: float) -> Optional[Sample]:
    """Decode a 64-byte passive telemetry packet (command 0x1A) from WITRN K2.

    Returns:
        Sample instance if valid telemetry packet, None if other command packet.
    Raises:
        ValueError on corrupt or invalid telemetry data.
    """
    data = normalize_input(raw)
    if not data or data[:2] != b"\xff\x55" or data[8] != 0x1A:
        return None

    if not (45 <= data[9] <= 52):
        raise ValueError(f"Invalid telemetry payload length: {data[9]}")
    if not dfu_checksum_matches(data):
        raise ValueError("Telemetry frame checksum mismatch")

    # Time counters between Ah/Wh and D+/D- are uint32
    ah, wh = struct.unpack_from("<2f", data, 14)
    rectime, uptime = struct.unpack_from("<2I", data, 22)
    dp, dn, ti, to, voltage, current = struct.unpack_from("<6f", data, 30)

    if not all(math.isfinite(v) for v in (elapsed, voltage, current, ah, wh, dp, dn)):
        raise ValueError("Telemetry packet contains non-finite values")
    if elapsed < 0 or not (0 <= voltage <= 100) or abs(current) > 100:
        raise ValueError(f"Telemetry measurements out of valid bounds: V={voltage}, I={current}")

    def valid_temp(val: float, is_external: bool = False) -> Optional[float]:
        if math.isfinite(val) and -50 <= val <= 180:
            if is_external and val <= 0:
                return None
            return round(val, 2)
        return None

    abs_current = abs(current)
    resistance = round(voltage / abs_current, 3) if abs_current >= 0.001 else None

    return Sample(
        time=elapsed,
        voltage=round(voltage, 4),
        current=round(current, 4),
        power=round(voltage * abs_current, 4),
        signed_power=round(voltage * current, 4),
        resistance=resistance,
        temp_in=valid_temp(ti),
        temp_out=valid_temp(to, is_external=True),
        dp=round(dp, 3),
        dn=round(dn, 3),
        ah=round(ah, 5),
        wh=round(wh, 5),
        record_seconds=rectime,
        uptime=uptime,
        group=data[54] + 1 if len(data) > 54 else None,
        segment=0,
    )


class Sampler:
    """Fixed-slot downsampler to avoid time jitter drift during recording."""
    def __init__(self, rate: int = 10):
        if rate not in (0, 1, 10, 50, 100):
            raise ValueError("Rate must be 0 (all), 1, 10, 50, or 100 Hz")
        self.interval = 1.0 / rate if rate > 0 else 0.0
        self.last_slot = None

    def accept(self, timestamp: float) -> bool:
        if not math.isfinite(timestamp) or timestamp < 0:
            raise ValueError("Invalid sample timestamp")
        if self.interval == 0.0:
            return True
        slot = math.floor(timestamp / self.interval + 1e-9)
        if self.last_slot is None or slot > self.last_slot:
            self.last_slot = slot
            return True
        return False
