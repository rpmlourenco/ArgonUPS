"""Incremental decoder for the Argon UPS serial status protocol."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import IntEnum

STATUS_REQUEST = bytes.fromhex("fe 00 00 fe")
MAX_FRAME_SIZE = 259  # Header, one-byte payload length, command, payload, checksum.


class ReadCommand(IntEnum):
    """Only commands identified as queries in the official reader."""

    STATUS = 0
    CHARGE_CURRENT = 2
    VERSION = 4
    RTC = 5
    NEXT_START = 7


DIAGNOSTIC_COMMANDS = tuple(
    command for command in ReadCommand if command != ReadCommand.STATUS
)


def read_request(command: ReadCommand) -> bytes:
    """Reject write/unknown commands rather than providing a general sender."""
    command = ReadCommand(command)
    return bytes((0xFE, 0, command, (0xFE + command) & 0xFF))


@dataclass(frozen=True)
class Frame:
    command: int
    payload: bytes


@dataclass(frozen=True)
class DiagnosticReading:
    value: int | datetime | None
    payload: bytes


@dataclass(frozen=True)
class UPSStatus:
    """A validated status sample."""

    battery_percent: int
    on_battery: bool


def decode_status(payload: bytes) -> UPSStatus:
    if len(payload) < 2 or payload[0] > 100:
        raise ValueError("Invalid battery status payload")
    return UPSStatus(payload[0], payload[1] != 0)


def decode_diagnostic(command: ReadCommand, payload: bytes) -> DiagnosticReading:
    """Decode only documented fields; retain raw bytes for interpretation."""
    if command == ReadCommand.CHARGE_CURRENT:
        if len(payload) < 2:
            raise ValueError("Short current payload")
        return DiagnosticReading(int.from_bytes(payload[:2], "big"), payload)
    if command == ReadCommand.VERSION:
        if not payload:
            raise ValueError("Short version payload")
        return DiagnosticReading(payload[0], payload)
    if command not in (ReadCommand.RTC, ReadCommand.NEXT_START):
        raise ValueError("Not a diagnostic read command")
    size = 6 if command == ReadCommand.RTC else 5
    if len(payload) < size:
        raise ValueError("Short date payload")
    # No documented disabled-alarm encoding exists. Preserve these sentinel
    # patterns as unknown rather than claiming that the alarm is disabled.
    if command == ReadCommand.NEXT_START and payload[:size] in (
        bytes(size),
        b"\xff" * size,
    ):
        return DiagnosticReading(None, payload)
    fields = []
    for byte in payload[:size]:
        if byte >> 4 > 9 or byte & 0xF > 9:
            raise ValueError("Invalid BCD date")
        fields.append((byte >> 4) * 10 + (byte & 0xF))
    fields[0] += 2000
    # Official code converts UTC to local time on display. Never apply the
    # user's configured timezone to the raw bytes a second time.
    return DiagnosticReading(datetime(*fields, tzinfo=UTC), payload)


class FrameParser:
    """Recover checksum-validated frames across arbitrary read boundaries."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[Frame]:
        """Return valid frames, retaining incomplete candidates."""
        self._buffer.extend(data)
        statuses = []
        index = 0
        incomplete = None
        while index < len(self._buffer):
            if self._buffer[index] != 0xFE:
                index += 1
                continue
            if len(self._buffer) - index < 3:
                incomplete = index if incomplete is None else incomplete
                break
            length = self._buffer[index + 1]
            end = index + length + 4
            if end > len(self._buffer):
                incomplete = index if incomplete is None else incomplete
                # A damaged length must not hide a later complete valid frame.
                index += 1
                continue
            frame = self._buffer[index:end]
            if sum(frame[:-1]) & 0xFF != frame[-1]:
                index += 1
                continue
            statuses.append(Frame(frame[2], bytes(frame[3:-1])))
            index = end
            incomplete = None
        if incomplete is None:
            self._buffer.clear()
        else:
            self._buffer = self._buffer[incomplete:][-MAX_FRAME_SIZE:]
        return statuses


class StatusParser(FrameParser):
    """Backward-compatible status-only decoder."""

    def feed(self, data: bytes) -> list[UPSStatus]:
        statuses = []
        for frame in super().feed(data):
            if frame.command != ReadCommand.STATUS:
                continue
            try:
                statuses.append(decode_status(frame.payload))
            except ValueError:
                continue
        return statuses
