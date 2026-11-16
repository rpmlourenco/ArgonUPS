"""Protocol regressions using synthetic frames, not physical hardware."""

import pytest

from custom_components.argon_ups.protocol import STATUS_REQUEST, StatusParser, UPSStatus


def frame(payload=b"\x4b\x00", command=0):
    data = bytes([0xFE, len(payload), command]) + payload
    return data + bytes([sum(data) & 0xFF])


def test_request():
    assert STATUS_REQUEST == b"\xfe\x00\x00\xfe"


@pytest.mark.parametrize("battery", [0, 1, 50, 99, 100])
@pytest.mark.parametrize("state", [0, 1, 2, 255])
def test_status(battery, state):
    assert StatusParser().feed(frame(bytes([battery, state]))) == [
        UPSStatus(battery, state != 0)
    ]


@pytest.mark.parametrize("split", range(1, 6))
def test_fragmented_response(split):
    parser = StatusParser()
    response = frame()
    assert parser.feed(response[:split]) == []
    assert parser.feed(response[split:]) == [UPSStatus(75, False)]


def test_byte_at_a_time():
    parser = StatusParser()
    samples = []
    for byte in frame():
        samples.extend(parser.feed(bytes([byte])))
    assert samples == [UPSStatus(75, False)]


def test_invalid_checksum_and_recovery():
    bad = frame()[:-1] + b"\x00"
    parser = StatusParser()
    assert parser.feed(bad) == []
    assert parser.feed(frame()) == [UPSStatus(75, False)]


def test_noise_coalesced_frames_and_partial_tail():
    parser = StatusParser()
    assert parser.feed(b"garbage" + frame() + frame(b"\x00\x01") + b"\xfe") == [
        UPSStatus(75, False),
        UPSStatus(0, True),
    ]
    assert parser.feed(frame()[1:]) == [UPSStatus(75, False)]


def test_corrupt_length_does_not_hide_valid_frame():
    assert StatusParser().feed(b"\xfe\xff\x00" + frame()) == [UPSStatus(75, False)]


def test_echo_unknown_command_short_status_and_extended_payload():
    parser = StatusParser()
    assert parser.feed(STATUS_REQUEST + frame(b"\x05", 4) + frame(b"\x01")) == []
    assert parser.feed(frame(b"\x64\x01\x42")) == [UPSStatus(100, True)]


def test_out_of_range_battery_rejected():
    assert StatusParser().feed(frame(b"\x65\x00")) == []


def test_embedded_start_byte_and_modulo_checksum():
    assert StatusParser().feed(frame(b"\x64\xfe")) == [UPSStatus(100, True)]


def test_noise_buffer_bounded():
    parser = StatusParser()
    for _ in range(100):
        parser.feed(b"\xfe\xff" * 200)
    assert len(parser._buffer) <= 259
    assert parser.feed(frame())[-1] == UPSStatus(75, False)
