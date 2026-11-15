"""Unit tests for transport handling and SQLite URI safety."""
from pathlib import Path
import tempfile
import unittest

from witrn_k2.core.exporter import open_ro_sqlite, read_sqlite_samples
from witrn_k2.core.protocol import FRAME_SIZE, build_frame
from witrn_k2.core.recorder import Recorder
from witrn_k2.core.telemetry import Sample
from witrn_k2.core.transport import SimulatorTransport


class TestTransportAndCrossPlatform(unittest.TestCase):
    def test_open_ro_sqlite_uri_safety(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_uri.sqlite"
            recorder = Recorder(Path(tmpdir))
            recorder.start("test_uri", rate=10)
            sample = Sample(
                time=0.5, voltage=5.0, current=1.0, power=5.0, signed_power=5.0
            )
            recorder.feed(sample)
            recorder.stop()

            # Test open_ro_sqlite
            conn = open_ro_sqlite(db_path)
            self.assertIsNotNone(conn)
            row = conn.execute("SELECT COUNT(*) FROM samples").fetchone()
            self.assertEqual(row[0], 1)
            conn.close()

            # Test read_sqlite_samples generator
            samples = list(read_sqlite_samples(db_path))
            self.assertEqual(len(samples), 1)
            self.assertAlmostEqual(samples[0].voltage, 5.0)

    def test_simulator_transport(self):
        sim = SimulatorTransport()
        data = sim.read(100)
        self.assertEqual(len(data), FRAME_SIZE)
        self.assertEqual(data[:2], b"\xff\x55")
        written = sim.write(data)
        self.assertEqual(written, FRAME_SIZE)
        sim.close()


if __name__ == "__main__":
    unittest.main()
