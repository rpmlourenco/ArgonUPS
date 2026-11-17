"""Bounded, synchronous serial I/O; always call from an executor."""

import threading
import time

import serial

from .protocol import (
    DIAGNOSTIC_COMMANDS,
    DiagnosticReading,
    FrameParser,
    ReadCommand,
    UPSStatus,
    decode_diagnostic,
    decode_status,
    read_request,
)

BAUDRATE = 115200
RESPONSE_TIMEOUT = 3.0
READ_TIMEOUT = 0.1


class ArgonUPSError(Exception):
    """Communication did not produce a valid status sample."""

    def __init__(
        self,
        message: str,
        *,
        reason: str = "communication_error",
        raw_response: bytes = b"",
        response_payload: bytes | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.raw_response = raw_response
        self.response_payload = response_payload


class ArgonUPSClient:
    """Keep one serial connection, reopening it after any failed transaction."""

    def __init__(self, port: str) -> None:
        self.port = port
        self._serial: serial.Serial | None = None
        self._lock = threading.Lock()

    def query(self) -> UPSStatus:
        """Read the critical battery/power status."""
        return self._query(ReadCommand.STATUS)

    def query_diagnostic(self, command: ReadCommand) -> DiagnosticReading:
        """Read one optional field, never allowing a write command."""
        if command not in DIAGNOSTIC_COMMANDS:
            raise ValueError("Not an allowed diagnostic command")
        return self._query(ReadCommand(command))

    def _query(self, command: ReadCommand) -> UPSStatus | DiagnosticReading:
        request = read_request(command)
        with self._lock:
            received = bytearray()
            rejected_payload = None
            rejection = None
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
                if connection.write(request) != len(request):
                    raise ArgonUPSError("Incomplete status request write")
                deadline = time.monotonic() + RESPONSE_TIMEOUT
                parser = FrameParser()
                while time.monotonic() < deadline:
                    data = connection.read(min(connection.in_waiting or 1, 256))
                    received.extend(data)
                    del received[:-512]
                    for frame in parser.feed(data):
                        if frame.command != command:
                            continue
                        if not frame.payload:
                            # A zero-length matching frame is the request echo,
                            # not evidence of a returned diagnostic value.
                            continue
                        try:
                            if command == ReadCommand.STATUS:
                                return decode_status(frame.payload)
                            return decode_diagnostic(command, frame.payload)
                        except ValueError as err:
                            rejected_payload = frame.payload
                            rejection = str(err)
                            continue
                if rejection is not None:
                    raise ArgonUPSError(
                        f"Rejected UPS {command.name} payload: {rejection}",
                        reason="invalid_payload",
                        raw_response=bytes(received),
                        response_payload=rejected_payload,
                    )
                raise ArgonUPSError(
                    f"Timed out waiting for a valid UPS {command.name} response",
                    reason="no_matching_valid_response" if received else "no_response",
                    raw_response=bytes(received),
                )
            except ArgonUPSError:
                # An unsupported diagnostic command must not force repeated
                # port opens/DTR transitions on an otherwise healthy UPS.
                if command == ReadCommand.STATUS:
                    self._close_unlocked()
                raise
            except (OSError, serial.SerialException) as err:
                self._close_unlocked()
                raise ArgonUPSError(str(err), raw_response=bytes(received)) from err

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
