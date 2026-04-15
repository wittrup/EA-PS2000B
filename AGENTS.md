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

## Key Design Decision: Transient Remote Mode
Write methods use **transient** remote mode: `REMOTE_ON` → write → `REMOTE_OFF` (in `finally`). This allows simultaneous front-panel and web control. The device is in remote mode only for the duration of each serial transaction.

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
