"""Unit tests for analytics, statistics, and integration."""
import unittest
from witrn_k2.core.analytics import calculate_statistics, direction_area
from witrn_k2.core.telemetry import Sample


class TestAnalytics(unittest.TestCase):
    def test_direction_area(self):
        # Both positive
        pos, neg = direction_area(2.0, 4.0, 1.0)
        self.assertEqual(pos, 3.0)
        self.assertEqual(neg, 0.0)

        # Cross zero (-2 to +2 in 2s)
        pos, neg = direction_area(-2.0, 2.0, 2.0)
        self.assertAlmostEqual(pos, 1.0)
        self.assertAlmostEqual(neg, 1.0)

    def test_calculate_statistics(self):
        samples = [
            Sample(time=0.0, voltage=5.0, current=1.0, power=5.0, signed_power=5.0, temp_in=25.0),
            Sample(time=1.0, voltage=5.1, current=1.2, power=6.12, signed_power=6.12, temp_in=26.0),
            Sample(time=2.0, voltage=4.9, current=0.8, power=3.92, signed_power=3.92, temp_in=27.0),
        ]
        stats = calculate_statistics(samples)
        self.assertEqual(stats["count"], 3)
        self.assertEqual(stats["duration_sec"], 2.0)
        self.assertEqual(stats["channels"]["voltage"]["min"], 4.9)
        self.assertEqual(stats["channels"]["voltage"]["max"], 5.1)
        self.assertGreater(stats["energy"]["mah_forward"], 0.0)
        self.assertGreater(stats["energy"]["mwh_forward"], 0.0)


if __name__ == "__main__":
    unittest.main()
