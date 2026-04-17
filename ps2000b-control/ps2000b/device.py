"""
High-level PS2000B device interface.

All write methods use *transient* remote mode: they briefly enter remote
mode for the duration of the serial transaction and return to local mode
afterward, so the front-panel controls remain usable between web commands.

Usage:
    with PS2000B("COM6") as psu:
        ch1 = psu.get_status(0)
        print(ch1.voltage, ch1.current)
        psu.set_voltage(0, 12.0)
        psu.set_current(0, 2.0)
        psu.enable_output(0, True)
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import serial

from . import protocol as proto


@dataclass
class ChannelStatus:
    channel:   int
    voltage:   float        # Volts (actual measured)
    current:   float        # Amps  (actual measured)
    output_on: bool
    remote:    bool         # True if in remote-control mode
    timestamp: float = field(default_factory=time.time)

    def as_dict(self) -> dict:
        return {
            "channel":   self.channel,
            "voltage":   self.voltage,
            "current":   self.current,
            "output_on": self.output_on,
            "remote":    self.remote,
            "timestamp": self.timestamp,
        }


class PS2000BError(Exception):
    """Raised for device communication errors."""


class PS2000B:
    """
    Interface to the PS2000B dual-channel power supply.

    Args:
        port:    Serial port name, e.g. 'COM6' or '/dev/ttyUSB0'
        timeout: Read timeout in seconds (default 1.0)
    """

    RESPONSE_LEN = 11

    def __init__(self, port: str, timeout: float = 1.0):
        self.port    = port
        self.timeout = timeout
        self._ser: Optional[serial.Serial] = None
        self._lock   = threading.Lock()   # serializes all serial I/O

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def open(self) -> "PS2000B":
        if self._ser and self._ser.is_open:
            return self
        self._ser = serial.Serial(
            port     = self.port,
            baudrate = proto.BAUD_RATE,
            parity   = proto.PARITY,
            stopbits = proto.STOPBITS,
            bytesize = proto.BYTESIZE,
            timeout  = self.timeout,
            xonxoff  = False,
            rtscts   = False,
            dsrdtr   = False,
        )
        return self

    def close(self) -> None:
        if self._ser and self._ser.is_open:
            self._ser.close()

    def __enter__(self) -> "PS2000B":
        return self.open()

    def __exit__(self, *_) -> None:
        self.close()

    @property
    def is_open(self) -> bool:
        return self._ser is not None and self._ser.is_open

    def _ensure_open(self) -> None:
        if not self.is_open:
            raise PS2000BError(f"Not connected to {self.port}. Call open() first.")

    def _send(self, telegram: bytes) -> None:
        """Send a write telegram and consume the device's ACK response (caller holds lock)."""
        self._ser.reset_input_buffer()
        self._ser.write(telegram)
        # Device always replies with a 6-byte ACK: SD DN OBJ=0xFF error_code CS(2)
        ack = self._ser.read(proto.ACK_LEN)
        if len(ack) == proto.ACK_LEN:
            error_code = ack[3]
            if error_code != 0x00:
                raise PS2000BError(
                    f"Device returned error code 0x{error_code:02X} "
                    f"(see programming guide section 3.6)"
                )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_status(self, channel: int) -> ChannelStatus:
        """Query actual voltage, current and output state for one channel."""
        self._ensure_open()
        with self._lock:
            self._ser.reset_input_buffer()
            self._ser.write(proto.build_query(channel))
            raw = self._ser.read(self.RESPONSE_LEN)

        if len(raw) != self.RESPONSE_LEN:
            raise PS2000BError(
                f"Short read on channel {channel}: expected {self.RESPONSE_LEN} bytes, got {len(raw)}"
            )

        parsed = proto.parse_response(raw)
        return ChannelStatus(
            channel   = parsed["channel"],
            voltage   = parsed["voltage"],
            current   = parsed["current"],
            output_on = parsed["output_on"],
            remote    = parsed["remote"],
        )

    def get_all(self) -> list[ChannelStatus]:
        """Query both channels and return [ch0, ch1]."""
        return [self.get_status(0), self.get_status(1)]

    def get_setpoints(self, channel: int) -> dict:
        """Query the current voltage and current setpoints for a channel (OBJ 72)."""
        self._ensure_open()
        with self._lock:
            self._ser.reset_input_buffer()
            self._ser.write(proto.build_setpoint_query(channel))
            raw = self._ser.read(self.RESPONSE_LEN)
        if len(raw) != self.RESPONSE_LEN:
            raise PS2000BError(f"Short read on setpoint query ch{channel}")
        parsed = proto.parse_response(raw)
        return {"channel": channel, "voltage": parsed["voltage"], "current": parsed["current"]}

    def get_all_setpoints(self) -> list[dict]:
        """Query setpoints for both channels."""
        return [self.get_setpoints(0), self.get_setpoints(1)]

    # ------------------------------------------------------------------
    # Remote mode
    # ------------------------------------------------------------------

    def set_remote(self, channel: int, enabled: bool) -> None:
        """Switch a channel into remote-control mode (required before writing setpoints)."""
        self._ensure_open()
        code = proto.CTRL_REMOTE_ON if enabled else proto.CTRL_REMOTE_OFF
        with self._lock:
            self._send(proto.build_control_command(channel, code))

    # ------------------------------------------------------------------
    # Write  (each method acquires the lock for the full read-modify-write)
    # ------------------------------------------------------------------

    def set_voltage(self, channel: int, voltage: float) -> None:
        """Set the voltage setpoint.

        Enters remote mode for the duration of the write, then returns
        to local mode so the front panel stays usable.
        """
        self._ensure_open()
        with self._lock:
            self._send(proto.build_control_command(channel, proto.CTRL_REMOTE_ON))
            try:
                self._send(proto.build_set_voltage(channel, voltage))
            finally:
                self._send(proto.build_control_command(channel, proto.CTRL_REMOTE_OFF))

    def set_current(self, channel: int, current: float) -> None:
        """Set the current setpoint.

        Enters remote mode for the duration of the write, then returns
        to local mode so the front panel stays usable.
        """
        self._ensure_open()
        with self._lock:
            self._send(proto.build_control_command(channel, proto.CTRL_REMOTE_ON))
            try:
                self._send(proto.build_set_current(channel, current))
            finally:
                self._send(proto.build_control_command(channel, proto.CTRL_REMOTE_OFF))

    def set_output(self, channel: int, voltage: float, current: float) -> None:
        """Set both voltage and current setpoints in one locked transaction.

        Enters remote mode for the duration of the write, then returns
        to local mode so the front panel stays usable.
        """
        self._ensure_open()
        with self._lock:
            self._send(proto.build_control_command(channel, proto.CTRL_REMOTE_ON))
            try:
                self._send(proto.build_set_voltage(channel, voltage))
                self._send(proto.build_set_current(channel, current))
            finally:
                self._send(proto.build_control_command(channel, proto.CTRL_REMOTE_OFF))

    def enable_output(self, channel: int, enabled: bool) -> None:
        """Switch the output on or off.

        Enters remote mode for the duration of the write, then returns
        to local mode so the front panel stays usable.
        """
        self._ensure_open()
        with self._lock:
            self._send(proto.build_control_command(channel, proto.CTRL_REMOTE_ON))
            try:
                code = proto.CTRL_OUTPUT_ON if enabled else proto.CTRL_OUTPUT_OFF
                self._send(proto.build_control_command(channel, code))
            finally:
                self._send(proto.build_control_command(channel, proto.CTRL_REMOTE_OFF))

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def is_io_error(exc: BaseException) -> bool:
        """Return True if *exc* indicates a broken serial link (device
        powered off, USB unplugged, etc.) rather than a protocol-level error."""
        return isinstance(exc, (OSError, serial.SerialException))

    def reconnect(self) -> None:
        """Close the stale connection and reopen.

        Swallows errors during close (the old fd may already be dead).
        Raises on open failure so the caller can decide when to retry.
        After a successful open the input buffer is flushed and a short
        stabilization delay allows the device to finish initializing.
        """
        try:
            self.close()
        except Exception:
            # Stale fd — force-clear so open() creates a fresh one
            self._ser = None
        time.sleep(0.3)
        self.open()   # raises serial.SerialException if port is gone
        # Device may still be initializing after power-on — flush
        # any startup garbage and give it time to become ready.
        self._ser.reset_input_buffer()
        time.sleep(0.5)
        self._ser.reset_input_buffer()
