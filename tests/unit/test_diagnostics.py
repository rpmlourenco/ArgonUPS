"""Diagnostic queries are bounded and cannot send configuration commands."""

from unittest.mock import patch

import pytest

from custom_components.argon_ups.client import ArgonUPSClient, ArgonUPSError
from custom_components.argon_ups.protocol import (
    DIAGNOSTIC_COMMANDS,
    Frame,
    FrameParser,
    ReadCommand,
    decode_diagnostic,
    read_request,
)


def frame(command, payload):
    data = bytes((0xFE, len(payload), command)) + payload
    return data + bytes((sum(data) & 0xFF,))


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (0, "fe0000fe"),
        (2, "fe000200"),
        (4, "fe000402"),
    ],
)
def test_only_documented_read_requests(command, expected):
    assert read_request(command).hex() == expected


@pytest.mark.parametrize("command", [1, 3, 5, 6, 7, 8, 9, 10, -1, 255])
def test_unknown_and_write_commands_rejected_before_open(command):
    with patch("custom_components.argon_ups.client.serial.Serial") as serial:
        with pytest.raises(ValueError):
            read_request(command)
        with pytest.raises(ValueError):
            ArgonUPSClient("/dev/test").query_diagnostic(command)
        serial.assert_not_called()


@pytest.mark.parametrize("command", DIAGNOSTIC_COMMANDS)
@pytest.mark.parametrize("split", range(1, 10))
def test_fragmented_diagnostic_frames(command, split):
    payload = b"\x26\x11\x17\x09\x30\x45"
    response = frame(command, payload)
    parser = FrameParser()
    assert parser.feed(response[:split]) == []
    assert parser.feed(response[split:]) == [Frame(command, payload)]


def test_bad_checksum_recovery_and_command_separation():
    response = frame(4, b"\x02")
    parser = FrameParser()
    assert parser.feed(response[:-1] + b"\x00") == []
    assert parser.feed(frame(2, b"\x12\x34") + response) == [
        Frame(2, b"\x12\x34"),
        Frame(4, b"\x02"),
    ]


def test_current_version_and_extra_bytes():
    assert decode_diagnostic(ReadCommand.CHARGE_CURRENT, b"\x12\x34").value == 4660
    assert decode_diagnostic(ReadCommand.CHARGE_CURRENT, b"\xff\xff").value == 65535
    assert decode_diagnostic(ReadCommand.VERSION, b"\x12\x99").value == 18


@pytest.mark.parametrize(
    ("command", "payload"),
    [
        (ReadCommand.VERSION, b""),
        (ReadCommand.CHARGE_CURRENT, b"\x01"),
        (ReadCommand.STATUS, b"\x4b\x00"),
    ],
)
def test_invalid_and_short_diagnostic_payloads(command, payload):
    with pytest.raises(ValueError):
        decode_diagnostic(command, payload)


def test_client_filters_echo_and_unrelated_status_and_keeps_port_on_timeout():
    with patch("custom_components.argon_ups.client.serial.Serial") as factory:
        device = factory.return_value
        device.in_waiting = 64
        device.write.return_value = 4
        device.read.side_effect = [
            read_request(ReadCommand.VERSION),
            frame(0, b"\x4b\x00"),
            frame(4, b"\x09"),
        ]
        client = ArgonUPSClient("/dev/test")
        assert client.query_diagnostic(ReadCommand.VERSION).value == 9
        device.write.assert_called_once_with(bytes.fromhex("fe 00 04 02"))
        device.read.side_effect = None
        device.read.return_value = b""
        with patch(
            "custom_components.argon_ups.client.time.monotonic", side_effect=[0, 0, 4]
        ):
            with pytest.raises(ArgonUPSError):
                client.query_diagnostic(ReadCommand.CHARGE_CURRENT)
        device.close.assert_not_called()
        device.read.return_value = frame(0, b"\x4b\x00")
        assert client.query().battery_percent == 75
        factory.assert_called_once()
        client.close()
