"""Incremental decoder for the Argon UPS serial status protocol."""

from dataclasses import dataclass

STATUS_REQUEST = bytes.fromhex("fe 00 00 fe")
MAX_FRAME_SIZE = 259  # Header, one-byte payload length, command, payload, checksum.


@dataclass(frozen=True)
class UPSStatus:
    """A validated status sample."""

    battery_percent: int
    on_battery: bool


class StatusParser:
    """Recover status frames from noise, corruption and arbitrary read boundaries."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[UPSStatus]:
        """Return complete valid status samples, retaining incomplete candidates."""
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
            if frame[2] == 0 and length >= 2 and frame[3] <= 100:
                statuses.append(UPSStatus(frame[3], frame[4] != 0))
            index = end
            incomplete = None
        if incomplete is None:
            self._buffer.clear()
        else:
            self._buffer = self._buffer[incomplete:][-MAX_FRAME_SIZE:]
        return statuses
