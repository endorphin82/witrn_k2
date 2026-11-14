"""Transport abstraction for WITRN K2.

Supports native Linux /dev/hidraw nodes, cross-platform hidapi, and a realistic simulator.
"""
import glob
import math
import os
import random
import select
import struct
import time
from typing import Dict, List, Optional

from .protocol import FRAME_SIZE, ProtocolError

VID = 0x0716
PID = 0x5060


def find_k2_device() -> Optional[Dict]:
    """Auto-detect connected WITRN K2 device on Linux via sysfs and hidraw."""
    for hidraw_dir in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            base_name = os.path.basename(hidraw_dir)
            dev_path = f"/dev/{base_name}"
            uevent_file = os.path.join(hidraw_dir, "device", "uevent")
            if os.path.exists(uevent_file):
                with open(uevent_file, "r") as f:
                    content = f.read()
                # Check for WITRN VID 0716 and PID 5060
                if ("0716" in content or "00000716" in content) and ("5060" in content or "00005060" in content):
                    has_read = os.access(dev_path, os.R_OK)
                    has_write = os.access(dev_path, os.W_OK)
                    serial = "20230727"
                    for line in content.splitlines():
                        if line.startswith("HID_UNIQ="):
                            serial = line.split("=", 1)[1]
                    return {
                        "type": "linux_hidraw",
                        "path": dev_path,
                        "readable": has_read,
                        "writable": has_write,
                        "name": "WITRN K2",
                        "serial": serial,
                        "vid": VID,
                        "pid": PID,
                    }
        except Exception:
            continue

    # Fallback to cython-hidapi enumeration if sysfs match didn't find anything
    try:
        import hid
        devs = hid.enumerate(VID, PID)
        if devs:
            d = devs[0]
            return {
                "type": "hidapi",
                "path": d["path"].decode("utf-8", "ignore") if isinstance(d["path"], bytes) else str(d["path"]),
                "readable": True,
                "writable": True,
                "name": d.get("product_string") or "WITRN K2",
                "serial": d.get("serial_number") or "",
                "vid": VID,
                "pid": PID,
            }
    except Exception:
        pass

    return None


class LinuxHidrawTransport:
    """Fast, direct access to Linux /dev/hidrawX device node."""
    def __init__(self, dev_path: str):
        self.dev_path = dev_path
        if not os.path.exists(dev_path):
            raise FileNotFoundError(f"Device node {dev_path} not found")
        if not os.access(dev_path, os.R_OK):
            raise PermissionError(f"No read permission for {dev_path}. Run setup_udev.sh or sudo chmod 666 {dev_path}")

        # Open in non-blocking read/write mode
        self.fd = os.open(dev_path, os.O_RDWR | os.O_NONBLOCK)

    def write(self, frame: bytes) -> int:
        if len(frame) != FRAME_SIZE:
            raise ProtocolError(f"Frame must be exactly {FRAME_SIZE} bytes")
        written = os.write(self.fd, frame)
        return written

    def read(self, timeout_ms: int = 100) -> bytes:
        timeout_sec = max(0.001, timeout_ms / 1000.0)
        r, _, _ = select.select([self.fd], [], [], timeout_sec)
        if not r:
            return b""
        try:
            data = os.read(self.fd, FRAME_SIZE + 1)
            # Linux hidraw returns exactly 64 bytes for reports without report IDs
            if len(data) == FRAME_SIZE + 1 and data[0] == 0:
                data = data[1:]
            return data
        except BlockingIOError:
            return b""

    def close(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except Exception:
                pass
            self.fd = None


class HidTransport:
    """Cross-platform transport using hidapi."""
    def __init__(self, path: bytes):
        import hid
        self.device = hid.device()
        self.device.open_path(path if isinstance(path, bytes) else path.encode("utf-8"))
        self.device.set_nonblocking(0)

    def write(self, frame: bytes) -> int:
        if len(frame) != FRAME_SIZE:
            raise ProtocolError("Frame must be 64 bytes")
        count = self.device.write(b"\0" + frame)
        return FRAME_SIZE if count in (FRAME_SIZE, FRAME_SIZE + 1) else count

    def read(self, timeout_ms: int = 100) -> bytes:
        raw = self.device.read(FRAME_SIZE + 1, timeout_ms)
        if not raw:
            return b""
        raw = bytes(raw)
        if len(raw) == FRAME_SIZE + 1 and raw[0] == 0:
            return raw[1:]
        return raw

    def close(self):
        if self.device:
            self.device.close()
            self.device = None


class SimulatorTransport:
    """Simulates a live WITRN K2 charging cycle for development and offline testing."""
    def __init__(self, scenario: str = "pd_charging"):
        self.scenario = scenario
        self.start_time = time.monotonic()
        self.ah = 0.0
        self.wh = 0.0
        self.last_time = self.start_time
        self.uptime = 0
        self.record_time = 0

    def write(self, frame: bytes) -> int:
        return len(frame)

    def read(self, timeout_ms: int = 100) -> bytes:
        time.sleep(0.01)  # 100 Hz rate simulation
        now = time.monotonic()
        dt = now - self.last_time
        self.last_time = now
        t = now - self.start_time

        # Simulate charging: 9V PD negotiation then gradual taper
        base_v = 9.05 + 0.02 * math.sin(t * 1.5)
        if t < 5.0:
            target_i = 1.8 * (t / 5.0)
        elif t < 30.0:
            target_i = 1.8 - 0.02 * (t - 5.0)
        else:
            target_i = 1.3 - 0.01 * (t - 30.0)
        target_i = max(0.05, target_i) + 0.01 * (random.random() - 0.5)

        self.ah += (target_i * dt) / 3600.0
        self.wh += (base_v * target_i * dt) / 3600.0
        self.uptime = int(t)
        self.record_time = int(t)

        temp_in = 26.0 + min(15.0, t * 0.1)
        temp_out = 24.5 + min(10.0, t * 0.07)
        dp = 0.65 + 0.01 * math.sin(t * 2)
        dn = 0.55 + 0.01 * math.cos(t * 2)

        # Build 64-byte WITRN telemetry packet
        tick = int(t * 1000) & 0xFFFFFFFF
        header = bytearray([
            0xFF, 0x55,
            (tick // 1000) & 0xFF, (tick % 1000) & 0xFF,
            ((tick // 30) | 0x80) & 0xFF,
            (tick // 100) & 0xFF, (tick % 100) & 0xFF, (tick // 80) & 0xFF,
            0x1A, 52,  # Command 0x1A, payload length 52
            0, 0, 0, 0,  # Reserved
        ])

        payload = struct.pack(
            "<2f2I6f",
            self.ah, self.wh,
            self.record_time, self.uptime,
            dp, dn, temp_in, temp_out, base_v, target_i
        )
        # Pad to offset 54: group = 0, rest zeros up to index 62
        full_data = bytearray(header + payload)
        while len(full_data) < 54:
            full_data.append(0)
        full_data.append(0)  # group 1 (0-based)
        while len(full_data) < 62:
            full_data.append(0)

        inner_chk = sum(full_data[8:62]) & 0xFF
        outer_chk = sum(full_data[:62]) & 0xFF
        full_data.append(inner_chk)
        full_data.append(outer_chk)

        return bytes(full_data)

    def close(self):
        pass


def open_transport(force_simulator: bool = False):
    """Auto-detect WITRN K2 and return an open transport."""
    if force_simulator:
        return SimulatorTransport(), {"type": "simulator", "name": "WITRN K2 (Simulator)", "path": "sim"}

    dev = find_k2_device()
    if dev is None:
        raise OSError("WITRN K2 не виявлено. Перевірте підключення USB.")

    if not dev.get("readable") or not dev.get("writable"):
        raise PermissionError(
            f"Немає доступу до {dev.get('path')}. Виконайте:\n"
            f"  sudo ./setup_udev.sh\n"
            f"або тимчасово:\n"
            f"  sudo chmod 666 {dev.get('path')}"
        )

    if dev["type"] == "linux_hidraw":
        return LinuxHidrawTransport(dev["path"]), dev
    else:
        return HidTransport(dev["path"]), dev
