## Context Maintenance Rules
- Keep all existing information.
- Only add new information from the current thread/context.
- No repetition – information should only appear once.
- Keep the file as short, concise and easily processable as possible.
- The purpose is to be able to restore the LLM context on restart.

## Project
Python controller + web dashboard for the **EA Elektro-Automatik PS2000B** dual-channel lab power supply (42 V / 6 A per channel). Cross-platform (Windows + Raspberry Pi).

## Architecture
```
ps2000b-control/
  ps2000b/          Python package — device driver
    protocol.py       Telegram build/parse, checksum, constants
    device.py         PS2000B class — thread-safe high-level interface
    ports.py          Serial port discovery (USB VID-based)
  server/
    main.py           FastAPI app + lifespan (device open/close)
    api.py            REST routes (setpoints, enable, logging)
    ws.py             WebSocket live-stream (250 ms poll)
    logger.py         Background CSV logger
  static/             Dashboard (index.html, app.js, style.css)
  cli.py              Click CLI entry point
  mcp_server.py       MCP tool definitions (SSE + stdio transports)
  service/            systemd unit + install/uninstall scripts
```

All write paths flow through `device.py`. The MCP server wraps the REST API (no direct serial access). The FastAPI app mounts the MCP SSE transport at `/sse`.

## Serial Protocol
- RS-232 / USB-CDC: 115200 baud, odd parity, 8N1
- Telegram: `SD DN OBJ [DATA] CS(2)` — big-endian 16-bit checksum
- Query: 5 bytes → 11-byte response; Write: variable → 6-byte ACK
- Scaling: `raw = round(value / nominal * 25600)`
- OBJ 71 = status, OBJ 72 = setpoints, OBJ 50 = set voltage, OBJ 51 = set current, OBJ 54 = control

## Key Design Decisions
**Transient remote mode:** Write methods bracket each serial transaction with `REMOTE_ON` → write → `REMOTE_OFF` (in `finally`), keeping the front panel usable between web commands.

**Auto-reconnect:** When the device is powered off, the USB serial node disappears and I/O raises `OSError(5)`. The WS polling loop in `ws.py` detects errors, calls `device.reconnect()`, and retries every 5 s. `reconnect()` flushes the buffer and waits 0.5 s for the device to stabilize after power-on. `main.py` registers the device object before `open()` so the reconnect loop works even if the device is offline at startup. The dashboard shows an amber "Device offline" pill during reconnection and auto-recovers to green "Connected" once data flows again.

**USB identity:** VID `0x232E` (EA Elektro-Automatik), native CDC-ACM driver (`/dev/ttyACM0`). Stable symlink: `/dev/serial/by-id/usb-EA_Elektro-Automatik_PS_2342-06B_*`.

**Static asset caching:** `index.html` uses `?v=N` cache-busting on `app.js` and `style.css` links. Bump the version when changing frontend files.

## Deployment
- **Pi hostname:** `wittrpi`
- **Service:** `ps2000b-control.service` — user `wittr`, port `/dev/ttyACM0`, HTTP on `0.0.0.0:8181`
- **Deploy:** `scp` changed files → `sudo systemctl restart ps2000b-control`
- **Logs:** `journalctl -u ps2000b-control -f`

## Hardware Limits (hard — never exceed)
- Voltage: 0–42 V per channel
- Current: 0–6 A per channel

## MCP
13 tools exposed (get_status, get_setpoints, list_ports, set_channel, set_voltage, set_current, enable_channel, get_log_status, start_logging, stop_logging, get_log_download_url, configure_and_enable_channel, safe_shutdown). Resources: `psu://status`, `psu://setpoints`. Prompt: `ps2000b_safety_briefing`.
