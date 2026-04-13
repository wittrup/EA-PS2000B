"""
WebSocket endpoint that streams live readings to the dashboard.

The device instance is shared here as module-level state (single-process model).
The serial port is protected by a threading.Lock inside PS2000B, so concurrent
REST API calls and WebSocket polling cannot interleave at the byte level.
"""

import asyncio
import json
import time
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ps2000b import PS2000B

router = APIRouter()

_device: Optional[PS2000B] = None

POLL_INTERVAL  = 0.25   # seconds between pushed readings
ERROR_COOLDOWN = 1.0    # seconds to wait after a read error before retrying


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

            await asyncio.sleep(
                ERROR_COOLDOWN if "error" in payload else POLL_INTERVAL
            )

    except WebSocketDisconnect:
        pass


def _read_payload() -> dict:
    """Blocking read of both channels — called via asyncio.to_thread."""
    if _device is None or not _device.is_open:
        return {"error": "No device connected", "ts": time.time()}
    try:
        channels = _device.get_all()
        return {
            "ts":  time.time(),
            "ch1": channels[0].as_dict(),
            "ch2": channels[1].as_dict(),
        }
    except Exception as e:
        return {"error": str(e), "ts": time.time()}
