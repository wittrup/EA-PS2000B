# PS2000B Control

Cross-platform Python controller for the **EA Elektro-Automatik PS2000B** dual-channel power supply.
Runs on Windows and Linux (Raspberry Pi).

## Install

```bash
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

After `python cli.py serve`, open **http://localhost:8080** in a browser.

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

### Raspberry Pi / Nginx

Put Nginx in front to expose the dashboard on port 80:

```nginx
location / {
    proxy_pass         http://127.0.0.1:8080;
    proxy_http_version 1.1;
    proxy_set_header   Upgrade $http_upgrade;
    proxy_set_header   Connection "upgrade";
}
```

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
requirements.txt
```

## Protocol notes

- Interface: RS-232 / USB-CDC, **115200 baud, odd parity, 8 data bits, 1 stop bit**
- Telegram format: `SD DN OBJ [DATA] CS(2)` — big-endian 16-bit checksum over all preceding bytes
- Read query: 5 bytes (`SD DN OBJ CS CS`); device replies with 11 bytes
- Write commands: device replies with a 6-byte ACK; non-zero byte 4 indicates an error
- Remote mode (`OBJ 0x36`, mask `0x10`) must be enabled before any setpoint or control write
- Scaling: `raw = round(value / nominal * 25600)` where nominal voltage = 42 V, nominal current = 6 A
- All write methods enable remote mode automatically if the channel is still in local mode
