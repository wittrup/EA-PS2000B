"""
Cross-platform serial port discovery for the PS2000B.

EA Elektro-Automatik USB VID: 0x0403 (FTDI-based)
The PS2000B shows up as a standard USB-to-serial adapter.
"""

import sys
from typing import Optional

try:
    import serial.tools.list_ports as list_ports_tool
    _SERIAL_AVAILABLE = True
except ImportError:
    _SERIAL_AVAILABLE = False

# EA Elektro-Automatik USB vendor ID (native CDC-ACM, not FTDI)
EA_VID = 0x232E


def list_serial_ports() -> list[str]:
    """
    Return a list of available serial port names on the current platform.

    Windows: ['COM1', 'COM3', 'COM35', ...]
    Linux:   ['/dev/ttyUSB0', '/dev/ttyACM0', ...]
    """
    if not _SERIAL_AVAILABLE:
        raise RuntimeError("pyserial is not installed. Run: pip install pyserial")

    ports = list_ports_tool.comports()
    return sorted([p.device for p in ports])


def find_ps2000b() -> Optional[str]:
    """
    Try to auto-detect a PS2000B by scanning available ports for a matching VID.

    Returns the port name (e.g. 'COM35' or '/dev/ttyUSB0') if found, else None.
    Falls back to returning the first available port if VID matching finds nothing.
    """
    if not _SERIAL_AVAILABLE:
        return None

    ports = list_ports_tool.comports()

    # First pass: match by USB vendor ID
    for p in ports:
        if p.vid == EA_VID:
            return p.device

    # Second pass: match by description keyword
    for p in ports:
        desc = (p.description or "").lower()
        if "ea" in desc or "elektro" in desc or "ps2000" in desc:
            return p.device

    return None


def port_info(port_name: str) -> dict:
    """Return human-readable info about a specific port."""
    if not _SERIAL_AVAILABLE:
        return {"device": port_name}

    for p in list_ports_tool.comports():
        if p.device == port_name:
            return {
                "device":      p.device,
                "description": p.description,
                "hwid":        p.hwid,
                "vid":         f"0x{p.vid:04X}" if p.vid else None,
                "pid":         f"0x{p.pid:04X}" if p.pid else None,
                "manufacturer": p.manufacturer,
            }
    return {"device": port_name, "description": "Unknown"}
