#!/usr/bin/env python3
"""
PS2000B MCP Server

Exposes the PS2000B power supply as an MCP tool provider so Claude Desktop
(or any MCP client) can control the supply in natural language.

Wraps the PS2000B FastAPI REST server — no direct serial port access — so
it runs safely alongside the web dashboard without port conflicts.

The FastAPI server must be running before this MCP server is started:
    python cli.py serve --port COM6 --http-port 8080

Usage:
    python mcp_server.py                              # default http://localhost:8080
    python mcp_server.py --server-url http://pi:8080
    PS2000B_SERVER_URL=http://localhost:8181 python mcp_server.py

Claude Desktop config  (%APPDATA%\\Claude\\claude_desktop_config.json):
    {
      "mcpServers": {
        "ps2000b": {
          "command": "python",
          "args": [
            "C:\\\\path\\\\to\\\\ps2000b-control\\\\mcp_server.py",
            "--server-url", "http://localhost:8080"
          ]
        }
      }
    }
"""

import argparse
import json
import os

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# ── Config ────────────────────────────────────────────────────────────────────
# parse_known_args so the MCP framework's own argv flags don't cause errors
_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument(
    "--server-url",
    default=os.environ.get("PS2000B_SERVER_URL", "http://localhost:8080"),
    help="Base URL of the PS2000B FastAPI server",
)
_args, _ = _parser.parse_known_args()
BASE_URL: str = _args.server_url.rstrip("/")

# ── HTTP client ───────────────────────────────────────────────────────────────
_http = httpx.AsyncClient(base_url=BASE_URL, timeout=5.0)

# ── MCP application ───────────────────────────────────────────────────────────
mcp = FastMCP(
    name="PS2000B Power Supply",
    instructions=(
        "Controls an EA Elektro-Automatik PS2000B dual-channel lab power supply "
        f"via its REST API at {BASE_URL}. "
        "Hardware limits: 0–42 V and 0–6 A per channel. "
        "Always call get_status before enabling a channel. "
        "Use safe_shutdown to cut power to both channels at once."
    ),
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)


# ── HTTP helper ───────────────────────────────────────────────────────────────

async def _api(method: str, path: str, **kwargs) -> dict:
    """Make a request to the FastAPI server and return parsed JSON."""
    try:
        r = await _http.request(method, path, **kwargs)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json().get("detail", e.response.text)
        except Exception:
            detail = e.response.text
        raise RuntimeError(f"Server error {e.response.status_code}: {detail}") from None
    except httpx.RequestError as e:
        raise RuntimeError(
            f"Cannot reach PS2000B server at {BASE_URL}. "
            f"Is `python cli.py serve` running? ({e})"
        ) from None


# ── Tools: Monitoring ─────────────────────────────────────────────────────────

@mcp.tool()
async def get_status() -> dict:
    """Read the actual (measured) voltage, current, and output state for both
    channels of the PS2000B power supply.

    Returns live hardware readings — not setpoints.
    Use this to check what the PSU is physically outputting right now, and
    always call this before enabling a channel to verify the current state.
    """
    return await _api("GET", "/api/status")


@mcp.tool()
async def get_setpoints() -> dict:
    """Read the programmed voltage and current setpoints for both channels.

    These are the target values configured in the PSU, not the actual measured
    outputs. Use this to verify what values are set before making changes.
    """
    return await _api("GET", "/api/setpoints")


@mcp.tool()
async def list_ports() -> dict:
    """List all available serial ports on the machine running the PS2000B server.

    Useful for diagnosing connection problems or verifying the PSU is detected.
    The PS2000B typically appears as a USB serial port (FTDI chip, VID 0x0403).
    """
    return await _api("GET", "/api/ports")


# ── Tools: Channel control ────────────────────────────────────────────────────

@mcp.tool()
async def set_channel(channel: int, voltage: float, current: float) -> dict:
    """Set both voltage and current setpoints for a channel atomically.

    Prefer this over calling set_voltage and set_current separately when you
    need to configure both values for a channel at once.

    Args:
        channel: Channel number — 1 or 2.
        voltage: Setpoint voltage in Volts (0.0 – 42.0 V).
        current: Current limit in Amps (0.0 – 6.0 A).
    """
    if channel not in (1, 2):
        raise ValueError("channel must be 1 or 2")
    return await _api("POST", f"/api/channel/{channel}/set",
                      json={"voltage": voltage, "current": current})


@mcp.tool()
async def set_voltage(channel: int, voltage: float) -> dict:
    """Set only the voltage setpoint for a channel, leaving the current limit unchanged.

    Args:
        channel: Channel number — 1 or 2.
        voltage: Setpoint voltage in Volts (0.0 – 42.0 V).
    """
    if channel not in (1, 2):
        raise ValueError("channel must be 1 or 2")
    return await _api("POST", f"/api/channel/{channel}/set-voltage",
                      json={"voltage": voltage})


@mcp.tool()
async def set_current(channel: int, current: float) -> dict:
    """Set only the current limit setpoint for a channel, leaving voltage unchanged.

    Args:
        channel: Channel number — 1 or 2.
        current: Current limit in Amps (0.0 – 6.0 A).
    """
    if channel not in (1, 2):
        raise ValueError("channel must be 1 or 2")
    return await _api("POST", f"/api/channel/{channel}/set-current",
                      json={"current": current})


@mcp.tool()
async def enable_channel(channel: int, enabled: bool) -> dict:
    """Enable or disable the output of one channel.

    When enabled=True the channel starts delivering power at the configured
    setpoints. When enabled=False the output is shut off; setpoints are retained.

    Always call get_status first to confirm the current state and verify that
    the setpoints are correct before enabling.

    Args:
        channel: Channel number — 1 or 2.
        enabled: True to turn the output on, False to turn it off.
    """
    if channel not in (1, 2):
        raise ValueError("channel must be 1 or 2")
    return await _api("POST", f"/api/channel/{channel}/enable",
                      json={"enabled": enabled})


# ── Tools: Logging ────────────────────────────────────────────────────────────

@mcp.tool()
async def get_log_status() -> dict:
    """Check the current state of the CSV data logger running on the server.

    Returns whether logging is active, the filename, sample count, start time,
    and any error. Call this before starting or stopping logging to understand
    the current state.
    """
    return await _api("GET", "/api/log/status")


@mcp.tool()
async def start_logging(interval: float = 1.0, filename: str | None = None) -> dict:
    """Start background CSV logging of both channels on the server.

    Records actual voltage, current, output state, and setpoints for each
    channel at the specified interval. Log files are saved in the server's
    working directory. If logging is already running this is a no-op.

    Args:
        interval: Sample interval in seconds (0.1 – 60.0, default 1.0).
        filename: Optional CSV filename. Defaults to a timestamp-based name
                  like '2026-04-13_21-51-10.csv'.
    """
    body: dict = {"interval": interval}
    if filename is not None:
        body["filename"] = filename
    return await _api("POST", "/api/log/start", json=body)


@mcp.tool()
async def stop_logging() -> dict:
    """Stop the background CSV logger.

    The log file remains on disk and can be downloaded using
    get_log_download_url. Always call this before directing the user to
    download their data, to ensure the file is fully flushed to disk.
    """
    return await _api("POST", "/api/log/stop")


@mcp.tool()
async def get_log_download_url() -> dict:
    """Return the download URL for the current (or most recent) CSV log file.

    Returns the URL rather than the file contents to avoid loading potentially
    large datasets into the context. The user can open or download the URL
    directly in their browser.

    Returns a dict with 'url' (string) and 'available' (bool), plus log metadata.
    """
    status = await _api("GET", "/api/log/status")
    available = bool(status.get("filename"))
    return {
        "url": f"{BASE_URL}/api/log/download" if available else None,
        "available": available,
        "filename": status.get("filename", ""),
        "samples": status.get("samples", 0),
        "running": status.get("running", False),
    }


# ── Tools: Compound / convenience ─────────────────────────────────────────────

@mcp.tool()
async def configure_and_enable_channel(
    channel: int, voltage: float, current: float
) -> dict:
    """Set voltage, current, and enable the output of a channel in one step.

    Equivalent to calling set_channel followed by enable_channel(enabled=True).
    Use this when you want to bring a channel up to a specific output in a
    single operation. Example: 'configure channel 1 to 12 V / 2 A and enable it'.

    Args:
        channel: Channel number — 1 or 2.
        voltage: Setpoint voltage in Volts (0.0 – 42.0 V).
        current: Current limit in Amps (0.0 – 6.0 A).
    """
    if channel not in (1, 2):
        raise ValueError("channel must be 1 or 2")
    set_result = await _api("POST", f"/api/channel/{channel}/set",
                             json={"voltage": voltage, "current": current})
    enable_result = await _api("POST", f"/api/channel/{channel}/enable",
                                json={"enabled": True})
    return {"ok": True, "set": set_result, "enable": enable_result}


@mcp.tool()
async def safe_shutdown() -> dict:
    """Disable the output on BOTH channels immediately.

    Use this as an emergency stop or at the end of a test to ensure no power
    is being delivered. Does not change setpoints — call get_setpoints afterward
    if you need to verify the programmed values are still intact.
    """
    ch1 = await _api("POST", "/api/channel/1/enable", json={"enabled": False})
    ch2 = await _api("POST", "/api/channel/2/enable", json={"enabled": False})
    return {"ok": True, "ch1": ch1, "ch2": ch2}


# ── Resources ─────────────────────────────────────────────────────────────────

@mcp.resource("psu://status")
async def resource_status() -> str:
    """Live voltage, current, and output state for both PS2000B channels.
    Refreshed each time it is read."""
    data = await _api("GET", "/api/status")
    return json.dumps(data, indent=2)


@mcp.resource("psu://setpoints")
async def resource_setpoints() -> str:
    """Currently programmed voltage and current setpoints for both channels.
    Refreshed each time it is read."""
    data = await _api("GET", "/api/setpoints")
    return json.dumps(data, indent=2)


# ── Prompt ────────────────────────────────────────────────────────────────────

@mcp.prompt()
def ps2000b_safety_briefing() -> str:
    """Establish safe working context at the start of a PS2000B session."""
    return (
        "You are controlling an EA Elektro-Automatik PS2000B dual-channel lab power supply.\n"
        "\n"
        "Hardware limits (hard — never exceed):\n"
        "  Voltage: 0–42 V per channel\n"
        "  Current: 0–6 A per channel\n"
        "\n"
        "Workflow rules:\n"
        "1. Always call get_status before enabling a channel — verify the setpoints first.\n"
        "2. Prefer configure_and_enable_channel over separate set + enable calls.\n"
        "3. Call safe_shutdown immediately if anything unexpected happens.\n"
        "4. When the user says 'turn everything off' or 'emergency stop', call safe_shutdown.\n"
        "5. Call stop_logging before directing the user to download the CSV log.\n"
        "6. Do not start logging if get_log_status shows it is already running.\n"
        f"\nServer: {BASE_URL}"
    )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    print(f"PS2000B MCP server starting — REST API at {BASE_URL}", file=sys.stderr, flush=True)
    mcp.run()   # stdio transport — required for Claude Desktop
