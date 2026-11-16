"""Bounded, synchronous serial I/O; always call from an executor."""

import threading
import time

import serial

from .protocol import STATUS_REQUEST, StatusParser, UPSStatus

BAUDRATE = 115200
RESPONSE_TIMEOUT = 3.0
READ_TIMEOUT = 0.1


class ArgonUPSError(Exception):
    """Communication did not produce a valid status sample."""


class ArgonUPSClient:
    """Keep one serial connection, reopening it after any failed transaction."""

    def __init__(self, port: str) -> None:
        self.port = port
        self._serial: serial.Serial | None = None
        self._lock = threading.Lock()

    def query(self) -> UPSStatus:
        """Send only the read-status command and wait for a verified response."""
        with self._lock:
            try:
                if self._serial is None:
                    self._serial = serial.Serial(
                        port=self.port,
                        baudrate=BAUDRATE,
                        timeout=READ_TIMEOUT,
                        write_timeout=1,
                        exclusive=True,
                    )
                connection = self._serial
                # Never publish a sample left over from a previous transaction.
                connection.reset_input_buffer()
                if connection.write(STATUS_REQUEST) != len(STATUS_REQUEST):
                    raise ArgonUPSError("Incomplete status request write")
                deadline = time.monotonic() + RESPONSE_TIMEOUT
                parser = StatusParser()
                while time.monotonic() < deadline:
                    data = connection.read(min(connection.in_waiting or 1, 256))
                    if statuses := parser.feed(data):
                        return statuses[-1]
                raise ArgonUPSError("Timed out waiting for a valid UPS status response")
            except (OSError, serial.SerialException, ArgonUPSError) as err:
                self._close_unlocked()
                raise ArgonUPSError(str(err)) from err

    def close(self) -> None:
        """Close safely, including when a cancelled executor job is still running."""
        with self._lock:
            self._close_unlocked()

    def _close_unlocked(self) -> None:
        connection, self._serial = self._serial, None
        if connection is not None:
            try:
                connection.close()
            except (OSError, serial.SerialException):
                pass


def probe(port: str) -> None:
    """Validate a port without leaving a connection open."""
    client = ArgonUPSClient(port)
    try:
        client.query()
    finally:
        client.close()
