"""Tests for SmartMeter Emulator const."""
from custom_components.growatt_smartmeter_emulator.const import DOMAIN


def test_domain():
    """Test DOMAIN constant."""
    assert DOMAIN == "growatt_smartmeter_emulator"
