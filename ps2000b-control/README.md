# PS2000B Control

Cross-platform Python controller for the **EA Elektro-Automatik PS2000B** dual-channel power supply.
Runs on Windows and Linux (Raspberry Pi).

## Install

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

## CLI usage

```bash
# List ports (auto-detects PS2000B by USB VID)
python cli.py ports

# Read both channels
python cli.py --port COM35 status
python cli.py --port /dev/ttyUSB0 status

# Set setpoints
python cli.py --port COM35 set --ch 1 --voltage 12.5 --current 2.0

# Set only voltage or only current
python cli.py --port COM35 set --ch 1 --voltage 12.5 --current 2.0

# Enable / disable output
python cli.py --port COM35 enable --ch 1
python cli.py --port COM35 disable --ch 2

# Log both channels to CSV (Ctrl-C to stop)
python cli.py --port COM35 log --output data.csv --interval 0.5

# Start web dashboard
python cli.py serve --port COM35 --host 0.0.0.0 --http-port 8080

# Start dashboard with auto-logging from boot (good for headless Pi)
python cli.py serve --port /dev/ttyUSB0 --log-file /data/ps2000b.csv --log-interval 0.5
```

## Web dashboard

After `python cli.py serve`, open **http://localhost:8181** in a browser.

### Live monitoring
- Voltage + current readings for both channels, updated every 200 ms via WebSocket
- 24-second rolling history chart per channel
- Connection status pill (auto-reconnects on disconnect)

### Control
- Voltage and current setpoint sliders — drag or type a value and press Enter
- Output ON/OFF toggle per channel

### CSV logging
A logging bar sits at the bottom of the dashboard:

| Control | Description |
|---------|-------------|
| **▶ Start Logging** | Starts a background CSV logger on the server; filename defaults to a timestamp |
| **⏹ Stop Logging** | Stops logging; file stays on disk |
| **Interval (s)** | Sample rate in seconds (0.1 – 60, default 1.0) |
| **⬇ Download CSV** | Downloads the current log file directly from the server |

The logger runs inside the server process and shares the existing serial connection — no port conflicts.

Log columns: `timestamp`, `ch1_voltage`, `ch1_current`, `ch1_on`, `ch1_v_set`, `ch1_a_set`,
`ch2_voltage`, `ch2_current`, `ch2_on`, `ch2_v_set`, `ch2_a_set`.

#### Auto-logging on startup

Pass `--log-file` to `serve` to begin logging immediately when the server starts
(useful for a headless Raspberry Pi that should record data from boot):

```bash
python cli.py serve --port /dev/ttyUSB0 --log-file /data/ps2000b.csv --log-interval 1.0
```

### Raspberry Pi deployment

The following steps deploy the full system (web dashboard + MCP server) to a
Raspberry Pi and run it as a systemd service:

```bash
# 1. Copy the project to the Pi (from your dev machine)
scp -r ps2000b-control  pi-hostname:~/ps2000b-control

# 2. SSH in and create a virtualenv
ssh pi-hostname
cd ~/ps2000b-control
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Verify the USB serial device is present
ls /dev/ttyACM0   # or /dev/ttyUSB0

# 4. (If needed) Grant serial port access
sudo usermod -aG dialout $USER
# Log out and back in for the group change to take effect

# 5. Install and start the systemd service
sudo service/install.sh
```

The service runs the web dashboard, REST API, WebSocket, and MCP SSE transport
on port 8181. Everything starts automatically on boot.

#### Managing the service

```bash
sudo systemctl status  ps2000b-control
sudo systemctl stop    ps2000b-control
sudo systemctl restart ps2000b-control
journalctl -u ps2000b-control -f

# Remove the service entirely
sudo service/uninstall.sh
```

The unit file (`service/ps2000b-control.service`) defaults to
`/dev/ttyACM0` on port 8181, user `wittr`. Edit it before installing if
your setup differs.

#### Nginx reverse proxy (optional)

Put Nginx in front to expose the dashboard on port 80:

```nginx
location / {
    proxy_pass         http://127.0.0.1:8181;
    proxy_http_version 1.1;
    proxy_set_header   Upgrade $http_upgrade;
    proxy_set_header   Connection "upgrade";
}
```

## MCP Server

The MCP (Model Context Protocol) server is integrated into the FastAPI app.
When the `serve` command runs, an SSE endpoint is automatically available at `/sse`,
allowing any MCP client to control the power supply in natural language.

No separate process is needed — the web dashboard and MCP server share the same
port and serial connection.

### Connecting an MCP client

Any MCP client that supports SSE transport can connect directly:

```json
{
  "mcpServers": {
    "ps2000b": {
      "url": "http://<hostname>:8181/sse"
    }
  }
}
```

For example, with the Pi deployed as described above:

```json
{
  "mcpServers": {
    "ps2000b": {
      "url": "http://wittrpi:8181/sse"
    }
  }
}
```

### Claude Desktop (stdio transport)

Claude Desktop uses stdio, so it launches `mcp_server.py` as a subprocess.
The MCP server wraps the REST API — no direct serial port access.

Add to `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ps2000b": {
      "command": "python",
      "args": [
        "C:\\path\\to\\ps2000b-control\\mcp_server.py",
        "--server-url", "http://wittrpi:8181"
      ]
    }
  }
}
```

If using a virtualenv replace `"python"` with the full `.venv\Scripts\python.exe` path.
Restart Claude Desktop after editing the config.

### Testing with the MCP Inspector

```bash
npx @modelcontextprotocol/inspector
```

In the inspector UI, select **SSE** transport and enter `http://<hostname>:8181/sse`
as the URL, then click Connect.

### Available tools (13)

| Tool | Description |
|------|-------------|
| `get_status` | Actual measured V/A/on for both channels |
| `get_setpoints` | Programmed voltage + current targets |
| `list_ports` | Serial ports on the server host |
| `set_channel` | Set V + A for a channel atomically |
| `set_voltage` | Set voltage only |
| `set_current` | Set current limit only |
| `enable_channel` | Turn output on or off |
| `get_log_status` | Check logger state (running / samples / filename) |
| `start_logging` | Start CSV logging (interval, optional filename) |
| `stop_logging` | Stop logging and flush file |
| `get_log_download_url` | Get URL to download the CSV (not the data itself) |
| `configure_and_enable_channel` | Set V/A and enable in one step |
| `safe_shutdown` | Disable both channels immediately |

### Resources & prompt

- **`psu://status`** — live readings readable from Claude's context
- **`psu://setpoints`** — current programmed setpoints
- **`/ps2000b_safety_briefing`** — slash command to prime Claude with hardware limits and workflow rules at the start of a session

### Example conversations

> *"What is channel 1 outputting right now?"*
> → Claude calls `get_status`

> *"Configure channel 1 to 12 V / 2 A and enable it"*
> → Claude calls `configure_and_enable_channel(1, 12.0, 2.0)`

> *"Start logging every 500 ms"*
> → Claude calls `start_logging(interval=0.5)`

> *"Emergency stop"*
> → Claude calls `safe_shutdown`

---

## REST API

The server exposes a full REST API (see `/docs` for the interactive Swagger UI):

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/status` | Actual V/A/on for both channels |
| `GET` | `/api/setpoints` | Current setpoints for both channels |
| `GET` | `/api/ports` | Available serial ports |
| `POST` | `/api/channel/{n}/set` | Set voltage + current for channel n (1 or 2) |
| `POST` | `/api/channel/{n}/set-voltage` | Set voltage only |
| `POST` | `/api/channel/{n}/set-current` | Set current only |
| `POST` | `/api/channel/{n}/enable` | Enable/disable output `{"enabled": true}` |
| `GET` | `/api/log/status` | Logging state (running, filename, sample count) |
| `POST` | `/api/log/start` | Start logging `{"interval": 1.0}` |
| `POST` | `/api/log/stop` | Stop logging |
| `GET` | `/api/log/download` | Download current CSV log file |
| `WS` | `/ws` | Live stream of readings at 200 ms interval |
| `GET` | `/sse` | MCP SSE transport endpoint |

## Project structure

```
ps2000b/
  __init__.py       Package exports
  protocol.py       Telegram build/parse + checksum (low-level)
  device.py         PS2000B class — thread-safe high-level interface
  ports.py          Serial port discovery (cross-platform, VID-based)
server/
  main.py           FastAPI app entry point + lifespan (device open/close)
  api.py            REST route handlers
  ws.py             WebSocket live-streaming handler
  logger.py         Background CSV logger (runs inside the server process)
static/
  index.html        Dashboard markup
  app.js            Dashboard logic (WebSocket, charts, controls, logging UI)
  style.css         Dark theme styles
cli.py              Click CLI entry point
mcp_server.py       MCP tool definitions (mounted into FastAPI + stdio entry point)
requirements.txt
inspector-config.json  MCP inspector config for testing
service/
  install.sh        Install systemd service (run with sudo)
  uninstall.sh      Remove systemd service (run with sudo)
  ps2000b-control.service  systemd unit file
```

## Protocol notes

- Interface: RS-232 / USB-CDC, **115200 baud, odd parity, 8 data bits, 1 stop bit**
- Telegram format: `SD DN OBJ [DATA] CS(2)` — big-endian 16-bit checksum over all preceding bytes
- Read query: 5 bytes (`SD DN OBJ CS CS`); device replies with 11 bytes
- Write commands: device replies with a 6-byte ACK; non-zero byte 4 indicates an error
- Remote mode (`OBJ 0x36`, mask `0x10`) must be enabled before any setpoint or control write
- Scaling: `raw = round(value / nominal * 25600)` where nominal voltage = 42 V, nominal current = 6 A
- All write methods enable remote mode automatically if the channel is still in local mode
