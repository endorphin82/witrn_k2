"""Data export and import: Official WITRN CSV/SQLite, standard CSV, and JSON."""
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sqlite3
from typing import Dict, Generator, Iterable, List, Optional

from .analytics import calculate_statistics
from .telemetry import Sample

OFFICIAL_HEADER = (
    "Time(D.hh:mm:ss.ms)",
    "Voltage(V)",
    "Current(A)",
    "Power(W)",
    "Temp(°C)",
    "D+(V)",
    "D-(V)",
)


def format_elapsed_time(seconds: float) -> str:
    """Format seconds into WITRN official format: [D.]hh:mm:ss.mmm."""
    total_ms = round(seconds * 1000)
    days, remainder = divmod(total_ms, 86400000)
    hours, remainder = divmod(remainder, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    secs, ms = divmod(remainder, 1000)
    prefix = f"{days}." if days > 0 else ""
    return f"{prefix}{hours:02}:{minutes:02}:{secs:02}.{ms:03}"


def parse_elapsed_time(text: str) -> float:
    """Parse WITRN official time string into seconds."""
    text = str(text).strip()
    if text.startswith('="') and text.endswith('"'):
        text = text[2:-1]
    match = re.fullmatch(r"(?:(\d+)\.)?(\d{1,2}):(\d{2}):(\d{2})\.(\d{1,3})", text)
    if not match:
        raise ValueError(f"Invalid time format: {text}")
    days, hours, minutes, secs, ms = match.groups()
    total = (
        int(days or 0) * 86400 +
        int(hours) * 3600 +
        int(minutes) * 60 +
        int(secs) +
        int(ms.ljust(3, "0")) / 1000.0
    )
    return total


def read_sqlite_samples(
    db_path: Path,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    max_points: Optional[int] = None,
) -> Generator[Sample, None, None]:
    """Read samples from an SQLite recording file."""
    conn = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        query = "SELECT * FROM samples"
        conditions = []
        params = []
        if start_time is not None:
            conditions.append("time >= ?")
            params.append(start_time)
        if end_time is not None:
            conditions.append("time <= ?")
            params.append(end_time)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY time, id"

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

        # If max_points specified and dataset is larger, thin out samples
        if max_points and len(rows) > max_points:
            step = len(rows) / max_points
            indices = {int(i * step) for i in range(max_points)}
            indices.add(len(rows) - 1)
            selected_rows = [rows[i] for i in sorted(indices) if i < len(rows)]
        else:
            selected_rows = rows

        for r in selected_rows:
            yield Sample(
                time=r["time"],
                voltage=r["voltage"],
                current=r["current"],
                power=r["power"],
                signed_power=r["signed_power"],
                resistance=r["resistance"],
                temp_in=r["temp_in"],
                temp_out=r["temp_out"],
                dp=r["dp"],
                dn=r["dn"],
                ah=r["ah"],
                wh=r["wh"],
                record_seconds=r["record_seconds"],
                uptime=r["uptime"],
                group=r["group_id"],
                segment=r["segment"],
            )
    finally:
        conn.close()


def export_official_csv(samples_iter: Iterable[Sample], output_path: Path, metadata: Optional[Dict] = None):
    """Export samples to official WITRN-compatible CSV with UTF-8 BOM."""
    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    samples_list = list(samples_iter)
    total_time_str = format_elapsed_time(samples_list[-1].time if samples_list else 0.0)

    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        # Official CSV metadata rows
        writer.writerow(["Model", metadata.get("model", "WITRN K2") if metadata else "WITRN K2"])
        writer.writerow(["SUM", len(samples_list)])
        writer.writerow(["TotalTime", total_time_str])
        writer.writerow(["DateTime", datetime.now().strftime("%Y/%m/%d %H:%M:%S")])
        writer.writerow([])
        # Header row
        writer.writerow(OFFICIAL_HEADER)

        for s in samples_list:
            writer.writerow([
                format_elapsed_time(s.time),
                f"{s.voltage:.4f}",
                f"{s.current:.4f}",
                f"{s.power:.4f}",
                f"{s.temp_out:.1f}" if s.temp_out is not None else "",
                f"{s.dp:.3f}" if s.dp is not None else "",
                f"{s.dn:.3f}" if s.dn is not None else "",
            ])


def export_standard_csv(samples_iter: Iterable[Sample], output_path: Path):
    """Export all telemetry fields to standard CSV format."""
    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "time_sec", "voltage_v", "current_a", "power_w", "signed_power_w",
            "resistance_ohm", "temp_in_c", "temp_out_c", "dp_v", "dn_v",
            "ah", "wh", "record_sec", "uptime_sec", "group", "segment"
        ])
        for s in samples_iter:
            writer.writerow([
                f"{s.time:.3f}", f"{s.voltage:.4f}", f"{s.current:.4f}",
                f"{s.power:.4f}", f"{s.signed_power:.4f}",
                f"{s.resistance:.3f}" if s.resistance is not None else "",
                f"{s.temp_in:.2f}" if s.temp_in is not None else "",
                f"{s.temp_out:.2f}" if s.temp_out is not None else "",
                f"{s.dp:.3f}" if s.dp is not None else "",
                f"{s.dn:.3f}" if s.dn is not None else "",
                f"{s.ah:.5f}" if s.ah is not None else "",
                f"{s.wh:.5f}" if s.wh is not None else "",
                s.record_seconds or "", s.uptime or "",
                s.group or "", s.segment
            ])


def export_json(samples_iter: Iterable[Sample], output_path: Path, metadata: Optional[Dict] = None):
    """Export samples and session summary to JSON."""
    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    samples_list = list(samples_iter)
    stats = calculate_statistics(samples_list) if samples_list else {}

    data = {
        "metadata": {
            "model": "WITRN K2",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            **(metadata or {}),
        },
        "statistics": stats,
        "samples": [s.dictionary() for s in samples_list],
    }

    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def import_official_csv(input_path: Path) -> List[Sample]:
    """Import samples from an official WITRN CSV file."""
    inp = Path(input_path).expanduser().resolve()
    if not inp.exists():
        raise FileNotFoundError(f"File {inp} not found")

    samples = []
    with open(inp, "r", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.reader(f)
        header_found = False
        for row in reader:
            if not row:
                continue
            if row[0] == OFFICIAL_HEADER[0] or "Voltage(V)" in row:
                header_found = True
                continue
            if not header_found or len(row) < 4:
                continue

            try:
                t = parse_elapsed_time(row[0])
                v = float(row[1])
                i = float(row[2])
                p = float(row[3]) if len(row) > 3 and row[3] else v * abs(i)
                temp = float(row[4]) if len(row) > 4 and row[4] else None
                dp = float(row[5]) if len(row) > 5 and row[5] else None
                dn = float(row[6]) if len(row) > 6 and row[6] else None
                res = round(v / abs(i), 3) if abs(i) >= 0.001 else None

                samples.append(Sample(
                    time=t,
                    voltage=round(v, 4),
                    current=round(i, 4),
                    power=round(p, 4),
                    signed_power=round(v * i, 4),
                    resistance=res,
                    temp_out=temp,
                    dp=dp,
                    dn=dn,
                ))
            except Exception:
                continue

    return samples
