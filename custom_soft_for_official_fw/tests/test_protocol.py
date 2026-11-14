"""Unit tests for protocol building and parsing."""
import unittest
from witrn_k2.core.protocol import FRAME_SIZE, MAGIC, ProtocolError, build_frame, parse_frame


class TestProtocol(unittest.TestCase):
    def test_build_and_parse_frame(self):
        cmd = 0x1A
        payload = b"Hello WITRN K2!"
        frame = build_frame(cmd, payload)
        self.assertEqual(len(frame), FRAME_SIZE)
        self.assertEqual(frame[:2], MAGIC)

        packet = parse_frame(frame)
        self.assertEqual(packet.command, cmd)
        self.assertEqual(packet.payload, payload)

    def test_checksum_verification(self):
        frame = bytearray(build_frame(0x02, b"\x01\x02\x03"))
        # Corrupt inner checksum
        frame[62] ^= 0xFF
        with self.assertRaises(ProtocolError):
            parse_frame(bytes(frame))

        # Re-build and corrupt outer checksum
        frame = bytearray(build_frame(0x02, b"\x01\x02\x03"))
        frame[63] ^= 0xFF
        with self.assertRaises(ProtocolError):
            parse_frame(bytes(frame))


if __name__ == "__main__":
    unittest.main()
