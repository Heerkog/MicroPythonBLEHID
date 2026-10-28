import importlib.util
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import patch


class UUID:
    """Model the documented integer and buffer forms used by these host tests."""

    def __init__(self, value):
        if isinstance(value, int):
            if not 0 <= value <= 0xffff:
                raise ValueError("integer UUIDs must fit in 16 bits")
            self.data = struct.pack("<H", value)
        else:
            self.data = bytes(value)
            if len(self.data) not in (2, 4, 16):
                raise ValueError("UUID buffers must be 2, 4 or 16 bytes")

    def __bytes__(self):
        return self.data


# Only hardware-specific imports are replaced; payload parsing uses real struct.
bluetooth = types.ModuleType("bluetooth")
bluetooth.UUID = UUID
for flag in ("FLAG_READ", "FLAG_WRITE", "FLAG_NOTIFY", "FLAG_WRITE_NO_RESPONSE"):
    setattr(bluetooth, flag, 0)
micropython = types.ModuleType("micropython")
micropython.const = lambda value: value
spec = importlib.util.spec_from_file_location(
    "hid_services_under_test", Path(__file__).resolve().parents[1] / "hid_services.py"
)
hid_services = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {
    "bluetooth": bluetooth,
    "micropython": micropython,
    "esp32": types.ModuleType("esp32"),
}):
    spec.loader.exec_module(hid_services)


class AdvertiserTests(unittest.TestCase):
    def setUp(self):
        self.advertiser = object.__new__(hid_services.Advertiser)

    def test_32_bit_service_uuid_round_trip(self):
        for value in (0x12345678, 0xffffffff):
            with self.subTest(value=value):
                raw = value.to_bytes(4, "little")
                payload = self.advertiser.advertising_payload(services=[UUID(raw)])
                decoded = self.advertiser.decode_services(payload)
                self.assertEqual([bytes(uuid) for uuid in decoded], [raw])

    def test_literal_32_bit_service_uuid_payload(self):
        payload = b"\x05\x05\x78\x56\x34\x12"
        decoded = self.advertiser.decode_services(payload)
        self.assertEqual([bytes(uuid) for uuid in decoded], [b"\x78\x56\x34\x12"])

    def test_16_bit_service_uuid_round_trip(self):
        payload = self.advertiser.advertising_payload(services=[UUID(0x1812)])
        decoded = self.advertiser.decode_services(payload)
        self.assertEqual([bytes(uuid) for uuid in decoded], [b"\x12\x18"])

    def test_128_bit_service_uuid_round_trip(self):
        value = bytes(range(16))
        payload = self.advertiser.advertising_payload(services=[UUID(value)])
        decoded = self.advertiser.decode_services(payload)
        self.assertEqual([bytes(uuid) for uuid in decoded], [value])

    def test_no_service_uuids(self):
        payload = self.advertiser.advertising_payload()
        self.assertEqual(self.advertiser.decode_services(payload), [])


if __name__ == "__main__":
    unittest.main()
