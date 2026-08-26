"""
Low-level telegram protocol for EA Elektro-Automatik PS2000B.

Telegram structure (read response, 11 bytes):
  Byte 0    SD  Start delimiter (bit-packed: data_len[0:3], dir[4], cast[5], trans[6:8])
  Byte 1    DN  Device node / channel (0 or 1)
  Byte 2    OBJ Object identifier
  Byte 3    QDS Query device state  (00=free, 01=remote)
  Byte 4    ST  Status byte         (bit 0 = output on)
  Bytes 5-6 AV  Actual voltage  (big-endian uint16, value = V/Unom * 25600)
  Bytes 7-8 AC  Actual current  (big-endian uint16, value = A/Inom * 25600)
  Bytes 9-10 CS Checksum (big-endian uint16 = sum of all preceding bytes)

Query telegram (5 bytes, no data field):
  SD DN OBJ CS_hi CS_lo
  75 00 47 00 BC  → channel 0
  75 01 47 00 BD  → channel 1

Source: EA PS2000B object_list_ps2000b_de_en.pdf (USB stick /Programming/)
"""

import struct

# Fallback device limits, only used if the nominal voltage/current can't be
# read from the device (OBJ 2 / OBJ 3). PS2000B.open() queries the real
# values at connect time since every model in the series has different
# ratings (e.g. PS2042-06B = 42 V/6 A, PS2384-05B = 84 V/5 A).
MAX_VOLTAGE = 42.0   # Volts  (OBJ 2: Nominal voltage)
MAX_CURRENT = 6.0    # Amps   (OBJ 3: Nominal current)
SCALE = 25600        # Full-scale raw value (100% × 256)

# Serial settings
BAUD_RATE   = 115200
PARITY      = "O"    # Odd
STOPBITS    = 1
BYTESIZE    = 8

# Object IDs (from object_list_ps2000b_de_en.pdf)
OBJ_DEVICE_TYPE     = 0x00  # 0   — Device type string           (read, 16-byte string)
OBJ_NOMINAL_VOLTAGE = 0x02  # 2   — Nominal voltage Unom          (read, 4-byte float)
OBJ_NOMINAL_CURRENT = 0x03  # 3   — Nominal current Inom          (read, 4-byte float)
OBJ_STATUS         = 0x47   # 71  — Status + actual values      (read, 6 data bytes)
OBJ_SETPOINTS      = 0x48   # 72  — Status + current setpoints  (read, 6 data bytes)
OBJ_SET_VOLTAGE    = 0x32   # 50  — Set voltage setpoint        (write, 2 data bytes)
OBJ_SET_CURRENT    = 0x33   # 51  — Set current setpoint        (write, 2 data bytes)
OBJ_CONTROL        = 0x36   # 54  — Power supply control        (write, 2 data bytes)

# Read response lengths: header(3) + data + checksum(2)
# String objects (OBJ 0, 1, ...) are NOT padded to their declared max length —
# the device sends only the string content up to and including its NUL
# terminator, so the total response length varies. 21 is the upper bound
# (16-byte max data field); read up to this many bytes with a short
# per-call timeout and parse whatever actually arrived (checksum-verified).
DEVICE_TYPE_MAX_RESPONSE_LEN = 3 + 16 + 2   # 21 bytes
NOMINAL_RESPONSE_LEN         = 3 + 4 + 2    # 9 bytes — fixed-size float field

# Control codes for OBJ_CONTROL: [mask, value]  (see section 3.3 in programming guide)
# Confirmed from example in section 3.4.1: F1 00 36 10 10 01 47 = remote ON
CTRL_OUTPUT_ON   = bytes([0x01, 0x01])   # mask=0x01, bit0=1 → output on
CTRL_OUTPUT_OFF  = bytes([0x01, 0x00])   # mask=0x01, bit0=0 → output off
CTRL_REMOTE_ON   = bytes([0x10, 0x10])   # mask=0x10, bit4=1 → remote control on
CTRL_REMOTE_OFF  = bytes([0x10, 0x00])   # mask=0x10, bit4=0 → manual control

# ACK response length: device replies to every write with a 6-byte telegram
# SD(1) DN(1) OBJ=0xFF(1) error_code(1) CS(2) — error 0x00 = success
ACK_LEN = 6

# SD byte components
_DIR_TO_DEVICE   = 1 << 4
_CAST_TYPE       = 1 << 5
_TRANS_QUERY     = 0b01 << 6   # Query data
_TRANS_SEND      = 0b11 << 6   # Send data


def _sd_send(data_len: int) -> int:
    """Build SD byte for a send (write) telegram (control → device)."""
    return _TRANS_SEND | _CAST_TYPE | _DIR_TO_DEVICE | ((data_len - 1) & 0x0F)


def checksum(payload: bytes) -> int:
    """16-bit checksum: sum of all payload bytes truncated to uint16."""
    return sum(payload) & 0xFFFF


def verify_checksum(telegram: bytes) -> bool:
    """Verify the checksum of a received telegram (last 2 bytes = CS big-endian)."""
    if len(telegram) < 3:
        return False
    payload = telegram[:-2]
    received = struct.unpack(">H", telegram[-2:])[0]
    return checksum(payload) == received


def _build_query(channel: int, obj: int) -> bytes:
    """Generic 5-byte query telegram: SD DN OBJ CS_hi CS_lo."""
    if channel not in (0, 1):
        raise ValueError(f"Channel must be 0 or 1, got {channel}")
    SD = _TRANS_QUERY | _CAST_TYPE | _DIR_TO_DEVICE | 0x05
    payload = bytes([SD, channel, obj])
    return payload + struct.pack(">H", checksum(payload))


def build_query(channel: int) -> bytes:
    """
    Build a 5-byte status query telegram for the given channel (0 or 1).

    Confirmed bytes:
      channel 0 → 75 00 47 00 bc
      channel 1 → 75 01 47 00 bd

    Format: SD DN OBJ CS_hi CS_lo  (no data bytes in the query).
    SD data_length bits (0-3) = 5, which encodes the expected response data size (6-1=5).
    CS covers SD + DN + OBJ only.
    """
    if channel not in (0, 1):
        raise ValueError(f"Channel must be 0 or 1, got {channel}")
    return _build_query(channel, OBJ_STATUS)


def build_setpoint_query(channel: int) -> bytes:
    """Build a 5-byte setpoint query (OBJ 72) for the given channel."""
    return _build_query(channel, OBJ_SETPOINTS)


def build_device_type_query() -> bytes:
    """Build a query for the device type string (OBJ 0), e.g. 'PS 2384-05 B'."""
    return _build_query(0, OBJ_DEVICE_TYPE)


def build_nominal_voltage_query() -> bytes:
    """Build a query for the device's nominal voltage Unom (OBJ 2)."""
    return _build_query(0, OBJ_NOMINAL_VOLTAGE)


def build_nominal_current_query() -> bytes:
    """Build a query for the device's nominal current Inom (OBJ 3)."""
    return _build_query(0, OBJ_NOMINAL_CURRENT)


def parse_device_type_response(data: bytes) -> str:
    """Parse a device-type string response (OBJ 0): header(3) + NUL-terminated
    string (variable length, not padded) + checksum(2)."""
    if len(data) < 6:   # header(3) + at least NUL(1) + checksum(2)
        raise ValueError(f"Short device type response: got {len(data)} bytes")
    if not verify_checksum(data):
        raise ValueError("Checksum mismatch in device type response")
    raw = data[3:-2]
    return raw.split(b"\x00", 1)[0].decode("ascii", errors="replace")


def parse_nominal_response(data: bytes) -> float:
    """Parse a nominal voltage/current response (OBJ 2/3): header(3) + 4-byte big-endian float + checksum(2)."""
    if len(data) != NOMINAL_RESPONSE_LEN:
        raise ValueError(f"Expected {NOMINAL_RESPONSE_LEN} bytes, got {len(data)}")
    if not verify_checksum(data):
        raise ValueError("Checksum mismatch in nominal value response")
    return struct.unpack(">f", data[3:7])[0]


def parse_response(data: bytes, nominal_voltage: float = MAX_VOLTAGE,
                    nominal_current: float = MAX_CURRENT) -> dict:
    """
    Parse an 11-byte status response (OBJ 71).

    Args:
      nominal_voltage: device's Unom (OBJ 2), used to scale the raw value.
      nominal_current: device's Inom (OBJ 3), used to scale the raw value.

    Returns:
      channel   int    0 or 1
      voltage   float  actual voltage in Volts
      current   float  actual current in Amps
      output_on bool   True if output is enabled (ST bit 0)
      remote    bool   True if device is in remote-control mode (QDS bits 0-1 == 1)
      raw       dict   raw field values for debugging
    """
    if len(data) != 11:
        raise ValueError(f"Expected 11 bytes, got {len(data)}")

    sd, dn, obj, qds, st, av, ac, cs = struct.unpack(">5B3H", data)

    if not verify_checksum(data):
        raise ValueError(f"Checksum mismatch in response from channel {dn}")

    if obj not in (OBJ_STATUS, OBJ_SETPOINTS):
        raise ValueError(f"Unexpected OBJ 0x{obj:02X}")

    voltage = nominal_voltage * av / SCALE
    current = nominal_current * ac / SCALE

    return {
        "channel":   dn,
        "voltage":   round(voltage, 4),
        "current":   round(current, 4),
        "output_on": bool(st & 0x01),       # status byte bit 0
        "remote":    bool(qds & 0x01),       # QDS bits 0-1: 01 = remote
        "raw": {"sd": sd, "dn": dn, "obj": obj, "qds": qds, "st": st,
                "av": av, "ac": ac, "cs": cs},
    }


def _build_send(channel: int, obj: int, data: bytes) -> bytes:
    """Build a generic send telegram: SD DN OBJ [data] CS."""
    payload = bytes([_sd_send(len(data)), channel, obj]) + data
    return payload + struct.pack(">H", checksum(payload))


def build_control_command(channel: int, code: bytes) -> bytes:
    """
    Build a power-supply control telegram (OBJ 54).

    Use the CTRL_* constants:
      CTRL_OUTPUT_ON / CTRL_OUTPUT_OFF  — switch output
      CTRL_REMOTE_ON / CTRL_REMOTE_OFF  — switch remote mode
    """
    if channel not in (0, 1):
        raise ValueError(f"Channel must be 0 or 1, got {channel}")
    return _build_send(channel, OBJ_CONTROL, code)


def build_set_voltage(channel: int, voltage: float, nominal_voltage: float = MAX_VOLTAGE) -> bytes:
    """Build a telegram to set the voltage setpoint (OBJ 50)."""
    if channel not in (0, 1):
        raise ValueError(f"Channel must be 0 or 1, got {channel}")
    if not (0.0 <= voltage <= nominal_voltage):
        raise ValueError(f"Voltage {voltage} out of range [0, {nominal_voltage}]")
    raw = round(voltage / nominal_voltage * SCALE)
    return _build_send(channel, OBJ_SET_VOLTAGE, struct.pack(">H", raw))


def build_set_current(channel: int, current: float, nominal_current: float = MAX_CURRENT) -> bytes:
    """Build a telegram to set the current setpoint (OBJ 51)."""
    if channel not in (0, 1):
        raise ValueError(f"Channel must be 0 or 1, got {channel}")
    if not (0.0 <= current <= nominal_current):
        raise ValueError(f"Current {current} out of range [0, {nominal_current}]")
    raw = round(current / nominal_current * SCALE)
    return _build_send(channel, OBJ_SET_CURRENT, struct.pack(">H", raw))
