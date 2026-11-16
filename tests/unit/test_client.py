"""Serial transaction and reconnection tests with a fake serial device."""

from unittest.mock import MagicMock, patch

import pytest
import serial

from custom_components.argon_ups.client import ArgonUPSClient, ArgonUPSError, probe
from custom_components.argon_ups.protocol import STATUS_REQUEST, UPSStatus

RESPONSE = bytes.fromhex("fe 02 00 4b 01 4c")


@pytest.fixture
def connection():
    with patch("custom_components.argon_ups.client.serial.Serial") as factory:
        device = factory.return_value
        device.write.return_value = 4
        device.in_waiting = 1
        device.read.side_effect = [bytes([byte]) for byte in RESPONSE]
        yield factory, device


def test_fragmented_transaction(connection):
    factory, device = connection
    client = ArgonUPSClient("/dev/test")
    assert client.query() == UPSStatus(75, True)
    factory.assert_called_once_with(
        port="/dev/test",
        baudrate=115200,
        timeout=0.1,
        write_timeout=1,
        exclusive=True,
    )
    device.reset_input_buffer.assert_called_once()
    device.write.assert_called_once_with(STATUS_REQUEST)
    client.close()
    device.close.assert_called_once()


def test_reconnect_after_disconnect(connection):
    factory, device = connection
    client = ArgonUPSClient("/dev/test")
    device.read.side_effect = serial.SerialException("disconnected")
    with pytest.raises(ArgonUPSError, match="disconnected"):
        client.query()
    device.close.assert_called_once()
    device.read.side_effect = [RESPONSE]
    assert client.query() == UPSStatus(75, True)
    assert factory.call_count == 2
    device.read.side_effect = [RESPONSE]
    client.query()
    assert factory.call_count == 2  # Healthy connections stay open.
    assert device.reset_input_buffer.call_count == 3


def test_timeout_invalid_checksum_closes_port(connection):
    _, device = connection
    device.read.side_effect = None
    device.read.return_value = RESPONSE[:-1] + b"\x00"
    with patch(
        "custom_components.argon_ups.client.time.monotonic", side_effect=[0, 0, 4]
    ):
        with pytest.raises(ArgonUPSError, match="Timed out"):
            ArgonUPSClient("/dev/test").query()
    device.close.assert_called_once()


def test_open_failure_can_retry(connection):
    factory, _ = connection
    factory.side_effect = OSError("missing")
    client = ArgonUPSClient("/dev/test")
    with pytest.raises(ArgonUPSError, match="missing"):
        client.query()
    device = MagicMock(in_waiting=6)
    device.write.return_value = 4
    device.read.return_value = RESPONSE
    factory.side_effect = None
    factory.return_value = device
    assert client.query() == UPSStatus(75, True)


def test_short_write(connection):
    _, device = connection
    device.write.return_value = 2
    with pytest.raises(ArgonUPSError, match="Incomplete"):
        ArgonUPSClient("/dev/test").query()
    device.close.assert_called_once()


def test_probe_releases_connection_on_success_and_failure(connection):
    _, device = connection
    probe("/dev/test")
    device.close.assert_called_once()
    device.reset_mock()
    device.read.side_effect = OSError("read error")
    with pytest.raises(ArgonUPSError):
        probe("/dev/test")
    device.close.assert_called_once()
