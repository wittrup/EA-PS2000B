"""
WebSocket endpoint that streams live readings to the dashboard.

The device instance is shared here as module-level state (single-process model).
The serial port is protected by a threading.Lock inside PS2000B, so concurrent
REST API calls and WebSocket polling cannot interleave at the byte level.

When the device is powered off (USB device node disappears), the polling loop
automatically attempts reconnection.  Once the device is back, normal
operation resumes without a server restart.
"""

import asyncio
import json
import time
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ps2000b import PS2000B

router = APIRouter()

_device: Optional[PS2000B] = None

POLL_INTERVAL    = 0.25   # seconds between pushed readings
ERROR_COOLDOWN   = 1.0    # seconds to wait after a transient read error
OFFLINE_COOLDOWN = 5.0    # seconds between reconnection attempts


def set_device(device: PS2000B) -> None:
    global _device
    _device = device


def get_device() -> Optional[PS2000B]:
    return _device


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            payload = await asyncio.to_thread(_read_payload)
            try:
                await websocket.send_text(json.dumps(payload))
            except Exception:
                break   # client disconnected — exit cleanly

            if payload.get("device_offline"):
                await asyncio.sleep(OFFLINE_COOLDOWN)
            elif "error" in payload:
                await asyncio.sleep(ERROR_COOLDOWN)
            else:
                await asyncio.sleep(POLL_INTERVAL)

    except WebSocketDisconnect:
        pass


def _try_reconnect() -> bool:
    """Attempt to reconnect the device.  Returns True on success."""
    try:
        _device.reconnect()
        print(f"Reconnected to PS2000B on {_device.port}", flush=True)
        return True
    except Exception as e:
        print(f"Reconnect failed: {e!r}", flush=True)
        return False


def _read_channels() -> dict:
    """Read both channels and return a success payload."""
    channels = _device.get_all()
    return {
        "ts":  time.time(),
        "ch1": channels[0].as_dict(),
        "ch2": channels[1].as_dict(),
    }


_OFFLINE_PAYLOAD = {
    "error": "Device offline \u2014 reconnecting\u2026",
    "device_offline": True,
}


def _read_payload() -> dict:
    """Blocking read of both channels \u2014 called via asyncio.to_thread.

    On any serial error (I/O failure, short read, etc.) this attempts a
    reconnect so the dashboard recovers automatically.
    """
    if _device is None:
        return {"error": "No device connected", "ts": time.time()}

    # Ensure the port is open (handles startup-offline and stale-fd cases)
    if not _device.is_open:
        if not _try_reconnect():
            return {**_OFFLINE_PAYLOAD, "ts": time.time()}

    try:
        return _read_channels()
    except Exception:
        # Read failed \u2014 connection may be stale or device still booting.
        # Try one reconnect + read cycle before reporting offline.
        if _try_reconnect():
            try:
                return _read_channels()
            except Exception:
                pass
        return {**_OFFLINE_PAYLOAD, "ts": time.time()}
