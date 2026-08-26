"""REST API routes for the PS2000B dashboard."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional

from ps2000b.ports import list_serial_ports, port_info
from ps2000b.device import PS2000BError
from .ws import get_device
from .logger import device_logger

router = APIRouter()


# ── Models ──────────────────────────────────────────────────────────────────

class SetpointRequest(BaseModel):
    # Upper bound is enforced against the connected device's actual nominal
    # voltage/current (ps2000b.device.PS2000B.nominal_voltage/current) inside
    # the route handler, since it varies by PS2000B model.
    voltage: float = Field(..., ge=0.0, description="Setpoint voltage in Volts")
    current: float = Field(..., ge=0.0, description="Setpoint current in Amps")

class VoltageRequest(BaseModel):
    voltage: float = Field(..., ge=0.0)

class CurrentRequest(BaseModel):
    current: float = Field(..., ge=0.0)


class EnableRequest(BaseModel):
    enabled: bool

class LogStartRequest(BaseModel):
    filename: Optional[str] = Field(None, description="CSV filename (default: timestamp-based)")
    interval: float = Field(1.0, ge=0.1, le=60.0, description="Sample interval in seconds")


# ── Routes ──────────────────────────────────────────────────────────────────

@router.get("/ports")
async def get_ports():
    """List all available serial ports."""
    ports = list_serial_ports()
    return {"ports": [port_info(p) for p in ports]}


@router.get("/device")
async def get_device_info():
    """Return the connected device's model and nominal (max) voltage/current."""
    device = get_device()
    if device is None:
        raise HTTPException(503, detail="No device connected")
    return {
        "device_type":     device.device_type,
        "nominal_voltage": device.nominal_voltage,
        "nominal_current": device.nominal_current,
    }


@router.get("/setpoints")
async def get_setpoints():
    """Read the current voltage and current setpoints from both channels."""
    device = get_device()
    if device is None:
        raise HTTPException(503, detail="No device connected")
    try:
        return {"setpoints": device.get_all_setpoints()}
    except Exception as e:
        raise HTTPException(502, detail=str(e))


@router.get("/status")
async def get_status():
    """Read actual voltage, current, and output state from both channels."""
    device = get_device()
    if device is None:
        raise HTTPException(503, detail="No device connected")
    try:
        channels = device.get_all()
        return {"channels": [ch.as_dict() for ch in channels]}
    except PS2000BError as e:
        raise HTTPException(502, detail=str(e))


@router.post("/channel/{channel}/set")
async def set_channel(channel: int, body: SetpointRequest):
    """Set both voltage and current setpoints for a channel (1 or 2)."""
    if channel not in (1, 2):
        raise HTTPException(400, detail="Channel must be 1 or 2")
    device = get_device()
    if device is None:
        raise HTTPException(503, detail="No device connected")
    try:
        device.set_output(channel - 1, body.voltage, body.current)
        result = device.get_status(channel - 1)
        return {"ok": True, "channel": result.as_dict()}
    except ValueError as e:
        raise HTTPException(422, detail=str(e))
    except PS2000BError as e:
        raise HTTPException(502, detail=str(e))


@router.post("/channel/{channel}/set-voltage")
async def set_voltage(channel: int, body: VoltageRequest):
    """Set only the voltage setpoint for a channel (1 or 2)."""
    if channel not in (1, 2):
        raise HTTPException(400, detail="Channel must be 1 or 2")
    device = get_device()
    if device is None:
        raise HTTPException(503, detail="No device connected")
    try:
        device.set_voltage(channel - 1, body.voltage)
        result = device.get_status(channel - 1)
        return {"ok": True, "channel": result.as_dict()}
    except ValueError as e:
        raise HTTPException(422, detail=str(e))
    except PS2000BError as e:
        raise HTTPException(502, detail=str(e))


@router.post("/channel/{channel}/set-current")
async def set_current(channel: int, body: CurrentRequest):
    """Set only the current setpoint for a channel (1 or 2)."""
    if channel not in (1, 2):
        raise HTTPException(400, detail="Channel must be 1 or 2")
    device = get_device()
    if device is None:
        raise HTTPException(503, detail="No device connected")
    try:
        device.set_current(channel - 1, body.current)
        result = device.get_status(channel - 1)
        return {"ok": True, "channel": result.as_dict()}
    except ValueError as e:
        raise HTTPException(422, detail=str(e))
    except PS2000BError as e:
        raise HTTPException(502, detail=str(e))


@router.get("/log/status")
async def log_status():
    """Return current logging state (running, filename, sample count)."""
    return device_logger.status.as_dict()


@router.post("/log/start")
async def log_start(body: LogStartRequest):
    """Start background CSV logging."""
    if get_device() is None:
        raise HTTPException(503, detail="No device connected")
    status = device_logger.start(filename=body.filename, interval=body.interval)
    return status.as_dict()


@router.post("/log/stop")
async def log_stop():
    """Stop background CSV logging."""
    status = device_logger.stop()
    return status.as_dict()


@router.get("/log/download")
async def log_download():
    """Download the current (or most recent) CSV log file."""
    path = device_logger.file_path()
    if path is None or not path.exists():
        raise HTTPException(404, detail="No log file available")
    return FileResponse(
        path        = str(path),
        media_type  = "text/csv",
        filename    = path.name,
    )


@router.post("/channel/{channel}/enable")
async def enable_channel(channel: int, body: EnableRequest):
    """Enable or disable the output of a channel (1 or 2)."""
    if channel not in (1, 2):
        raise HTTPException(400, detail="Channel must be 1 or 2")
    device = get_device()
    if device is None:
        raise HTTPException(503, detail="No device connected")
    try:
        device.enable_output(channel - 1, body.enabled)
        result = device.get_status(channel - 1)
        return {"ok": True, "channel": result.as_dict()}
    except PS2000BError as e:
        raise HTTPException(502, detail=str(e))
