"""Core driver and communication components for WITRN K2."""
from .protocol import FRAME_SIZE, ProtocolError, build_frame, parse_frame
from .telemetry import Sample, decode_report, dfu_checksum_matches, Sampler
from .transport import LinuxHidrawTransport, HidTransport, SimulatorTransport, find_k2_device, open_transport
from .recorder import Recorder, RecordingSession, AutoStopRule
from .analytics import (
    calculate_statistics,
    detect_peaks,
    detect_phases,
    direction_area,
    interpolate_sample,
    moving_average,
    build_report,
)
from .exporter import export_official_csv, export_standard_csv, export_json, import_official_csv, open_ro_sqlite
from .svgcharts import export_samples_svg

__all__ = [
    "FRAME_SIZE",
    "ProtocolError",
    "build_frame",
    "parse_frame",
    "Sample",
    "decode_report",
    "dfu_checksum_matches",
    "Sampler",
    "LinuxHidrawTransport",
    "HidTransport",
    "SimulatorTransport",
    "find_k2_device",
    "open_transport",
    "Recorder",
    "RecordingSession",
    "AutoStopRule",
    "calculate_statistics",
    "direction_area",
    "interpolate_sample",
    "moving_average",
    "detect_peaks",
    "detect_phases",
    "build_report",
    "export_samples_svg",
    "export_official_csv",
    "export_standard_csv",
    "export_json",
    "import_official_csv",
    "open_ro_sqlite",
]
