"""
FastAPI application entry point.

Serves:
  GET  /                          → dashboard HTML
  GET  /api/ports                 → available serial ports
  GET  /api/status                → current readings (both channels)
  POST /api/channel/{n}/set       → set voltage + current setpoints
  POST /api/channel/{n}/enable    → enable/disable output
  WS   /ws                        → live stream of readings (200 ms interval)
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

import serial
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import router as api_router
from .ws import router as ws_router, set_device
from .logger import device_logger
from ps2000b import PS2000B
from ps2000b.ports import find_ps2000b

STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    port = os.environ.get("PS2000B_PORT") or find_ps2000b()
    device = None
    if not port:
        print("WARNING: No PS2000B port found. Dashboard will load but show no data.")
    else:
        try:
            device = PS2000B(port)
            device.open()
            set_device(device)
            device_logger.set_device(device)
            print(f"Connected to PS2000B on {port}")

            # Auto-start logging if a log file was specified
            log_file = os.environ.get("PS2000B_LOG_FILE")
            log_interval = float(os.environ.get("PS2000B_LOG_INTERVAL", "1.0"))
            if log_file:
                device_logger.start(filename=log_file, interval=log_interval)
                print(f"Auto-logging to {log_file} every {log_interval}s")
        except serial.SerialException as e:
            print(f"WARNING: Could not open {port}: {e}")
            print("Dashboard will load. Fix the port conflict and restart.")
    yield
    if device:
        device_logger.stop()
        device.close()
        print("Serial connection closed.")


app = FastAPI(title="PS2000B Control", lifespan=lifespan)

app.include_router(api_router, prefix="/api")
app.include_router(ws_router)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def dashboard():
    return FileResponse(str(STATIC_DIR / "index.html"))

# Mount MCP SSE transport so the server is also an MCP endpoint at /sse
try:
    from mcp_server import mcp as _mcp_instance
    app.mount("/", _mcp_instance.sse_app())
except ImportError:
    pass  # mcp / httpx not installed — dashboard still works without MCP
