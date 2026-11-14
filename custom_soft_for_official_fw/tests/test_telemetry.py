"""Unit tests for telemetry decoding and rate sampler."""
import unittest
from witrn_k2.core.telemetry import Sample, Sampler, decode_report
from witrn_k2.core.transport import SimulatorTransport


class TestTelemetry(unittest.TestCase):
    def test_sampler_rate_limiting(self):
        sampler = Sampler(rate=10)  # 10 Hz = 0.1s interval
        self.assertTrue(sampler.accept(0.0))
        self.assertFalse(sampler.accept(0.05))
        self.assertTrue(sampler.accept(0.101))
        self.assertFalse(sampler.accept(0.15))
        self.assertTrue(sampler.accept(0.201))

    def test_decode_simulator_telemetry(self):
        sim = SimulatorTransport()
        raw = sim.read()
        sample = decode_report(raw, 1.234)
        self.assertIsNotNone(sample)
        self.assertIsInstance(sample, Sample)
        self.assertGreater(sample.voltage, 8.0)
        self.assertGreater(sample.power, 0.0)
        self.assertIsNotNone(sample.ah)
        self.assertIsNotNone(sample.wh)


if __name__ == "__main__":
    unittest.main()
