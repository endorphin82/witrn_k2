"""Unit tests for SQLite recorder and auto-stop rule."""
import tempfile
import unittest
from pathlib import Path

from witrn_k2.core.recorder import AutoStopRule, Recorder
from witrn_k2.core.telemetry import Sample


class TestRecorder(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.recorder = Recorder(Path(self.temp_dir.name))

    def tearDown(self):
        self.recorder.stop()
        self.temp_dir.cleanup()

    def test_record_lifecycle(self):
        self.assertFalse(self.recorder.is_recording)
        db_path = self.recorder.start("test_session", rate=10)
        self.assertTrue(self.recorder.is_recording)
        self.assertTrue(db_path.exists())

        sample = Sample(
            time=1.0, voltage=5.0, current=1.0, power=5.0, signed_power=5.0,
            resistance=5.0, temp_in=25.0, temp_out=24.0, dp=0.6, dn=0.5,
            ah=0.01, wh=0.05, record_seconds=1, uptime=10, group=1
        )
        self.recorder.feed(sample)
        status = self.recorder.get_status()
        self.assertEqual(status["count"], 1)

        saved_path = self.recorder.stop()
        self.assertFalse(self.recorder.is_recording)
        self.assertEqual(saved_path, db_path)

    def test_auto_stop(self):
        auto = AutoStopRule(enabled=True, kind="current", threshold=0.1, duration=1.0)
        self.recorder.start("auto_stop_session", rate=10, auto_rule=auto)

        # First sample under threshold
        s1 = Sample(time=1.0, voltage=5.0, current=0.05, power=0.25, signed_power=0.25)
        triggered = self.recorder.feed(s1)
        self.assertFalse(triggered)

        # Sample at 2.1s (1.1s > duration 1.0s) -> should trigger auto-stop
        s2 = Sample(time=2.1, voltage=5.0, current=0.04, power=0.2, signed_power=0.2)
        triggered = self.recorder.feed(s2)
        self.assertTrue(triggered)
        self.assertFalse(self.recorder.is_recording)


if __name__ == "__main__":
    unittest.main()
