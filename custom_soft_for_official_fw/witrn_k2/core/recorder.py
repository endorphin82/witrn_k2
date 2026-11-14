"""SQLite-backed telemetry recorder with WAL journal and auto-stop triggers."""
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from pathlib import Path
import sqlite3
import time
from typing import Dict, Generator, List, Optional

from .telemetry import Sample, Sampler

SCHEMA_VERSION = 1


@dataclass
class AutoStopRule:
    """Auto-stop condition (e.g. charge completion when current/power drops below threshold)."""
    enabled: bool = False
    kind: str = "current"  # "current" or "power"
    threshold: float = 0.05  # A or W
    duration: float = 10.0  # seconds

    def __post_init__(self):
        if self.kind not in ("current", "power"):
            raise ValueError("Auto-stop kind must be 'current' or 'power'")
        if self.threshold < 0 or self.duration < 0:
            raise ValueError("Threshold and duration must be non-negative")


class RecordingSession:
    """Encapsulates an open SQLite recording file."""
    def __init__(self, path: Path, rate: int = 10, metadata: Optional[Dict[str, str]] = None):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.rate = rate
        self.sampler = Sampler(rate)

        self.db = sqlite3.connect(str(self.path), check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)")
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time REAL NOT NULL,
                voltage REAL NOT NULL,
                current REAL NOT NULL,
                power REAL NOT NULL,
                signed_power REAL NOT NULL,
                resistance REAL,
                temp_in REAL,
                temp_out REAL,
                dp REAL,
                dn REAL,
                ah REAL,
                wh REAL,
                record_seconds INTEGER,
                uptime INTEGER,
                group_id INTEGER,
                segment INTEGER NOT NULL DEFAULT 0
            )
        """)
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_samples_time ON samples(time)")

        # Write initial metadata
        init_meta = {
            "schema": str(SCHEMA_VERSION),
            "model": "WITRN K2",
            "rate": str(rate),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "closed": "0",
            **(metadata or {})
        }
        self.db.executemany(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            list(init_meta.items())
        )
        self.db.commit()

        self.count = 0
        self.pending = 0
        self.last_commit = time.monotonic()
        self.start_sample_time: Optional[float] = None
        self.latest_sample_time: Optional[float] = None

    def append(self, sample: Sample):
        if self.start_sample_time is None:
            self.start_sample_time = sample.time
        self.latest_sample_time = sample.time

        self.db.execute("""
            INSERT INTO samples (
                time, voltage, current, power, signed_power, resistance,
                temp_in, temp_out, dp, dn, ah, wh, record_seconds,
                uptime, group_id, segment
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sample.time, sample.voltage, sample.current, sample.power,
            sample.signed_power, sample.resistance, sample.temp_in,
            sample.temp_out, sample.dp, sample.dn, sample.ah, sample.wh,
            sample.record_seconds, sample.uptime, sample.group, sample.segment
        ))
        self.pending += 1
        self.count += 1

        now = time.monotonic()
        if self.pending >= 100 or (now - self.last_commit) >= 1.0:
            self.commit()

    def commit(self):
        if self.db and self.pending > 0:
            self.db.commit()
            self.pending = 0
            self.last_commit = time.monotonic()

    def close(self, completed: bool = True):
        if self.db:
            try:
                self.commit()
                self.db.execute("INSERT OR REPLACE INTO metadata VALUES ('closed', ?)", ("1" if completed else "0",))
                self.db.execute("INSERT OR REPLACE INTO metadata VALUES ('total_count', ?)", (str(self.count),))
                self.db.commit()
                self.db.close()
            finally:
                self.db = None


class Recorder:
    """Manages active capture session, segments, sampling rate, and auto-stop."""
    def __init__(self, storage_dir: Path):
        self.storage_dir = Path(storage_dir).expanduser().resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.session: Optional[RecordingSession] = None
        self.is_paused = False
        self.segment = 0
        self.rate = 10
        self.auto_rule = AutoStopRule()
        self.auto_triggered_time: Optional[float] = None
        self.last_sample: Optional[Sample] = None

    @property
    def is_recording(self) -> bool:
        return self.session is not None and not self.is_paused

    def start(self, session_name: Optional[str] = None, rate: int = 10, auto_rule: Optional[AutoStopRule] = None) -> Path:
        if self.session is not None:
            raise RuntimeError("Recording session already in progress")

        self.rate = rate
        self.auto_rule = auto_rule or AutoStopRule()
        self.auto_triggered_time = None
        self.is_paused = False
        self.segment = 0

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = session_name.strip() if session_name else f"witrn_k2_{timestamp_str}"
        # Ensure valid filename
        safe_name = "".join(c for c in name if c.isalnum() or c in ("-", "_", " ")).strip()
        if not safe_name:
            safe_name = f"witrn_k2_{timestamp_str}"
        file_path = self.storage_dir / f"{safe_name}.sqlite"

        self.session = RecordingSession(file_path, rate=rate, metadata={"session_name": safe_name})
        return file_path

    def pause(self):
        if not self.session or self.is_paused:
            return
        self.session.commit()
        self.is_paused = True
        self.auto_triggered_time = None

    def resume(self):
        if not self.session or not self.is_paused:
            return
        self.is_paused = False
        self.segment += 1
        self.session.sampler = Sampler(self.rate)
        self.auto_triggered_time = None

    def stop(self) -> Optional[Path]:
        if not self.session:
            return None
        path = self.session.path
        self.session.close(completed=True)
        self.session = None
        self.is_paused = False
        self.auto_triggered_time = None
        return path

    def feed(self, sample: Sample) -> bool:
        """Feed a telemetry sample. Returns True if auto-stop triggered."""
        self.last_sample = sample
        if not self.is_recording or not self.session:
            return False

        # Segment tagging
        sample_with_segment = Sample(
            time=sample.time,
            voltage=sample.voltage,
            current=sample.current,
            power=sample.power,
            signed_power=sample.signed_power,
            resistance=sample.resistance,
            temp_in=sample.temp_in,
            temp_out=sample.temp_out,
            dp=sample.dp,
            dn=sample.dn,
            ah=sample.ah,
            wh=sample.wh,
            record_seconds=sample.record_seconds,
            uptime=sample.uptime,
            group=sample.group,
            segment=self.segment,
        )

        if self.session.sampler.accept(sample.time):
            self.session.append(sample_with_segment)

        # Check auto-stop condition
        if self.auto_rule.enabled and self.auto_rule.duration > 0:
            val = abs(sample.current) if self.auto_rule.kind == "current" else sample.power
            if val < self.auto_rule.threshold:
                if self.auto_triggered_time is None:
                    self.auto_triggered_time = sample.time
                elif sample.time - self.auto_triggered_time >= self.auto_rule.duration:
                    self.stop()
                    return True
            else:
                self.auto_triggered_time = None

        return False

    def get_status(self) -> Dict:
        return {
            "is_recording": self.is_recording,
            "is_paused": self.is_paused,
            "segment": self.segment,
            "rate": self.rate,
            "count": self.session.count if self.session else 0,
            "file_path": str(self.session.path) if self.session else None,
            "auto_stop_enabled": self.auto_rule.enabled,
        }
