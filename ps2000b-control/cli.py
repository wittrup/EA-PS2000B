#!/usr/bin/env python3
"""
PS2000B Command Line Interface

Examples:
  python cli.py ports
  python cli.py --port COM35 status
  python cli.py --port COM35 set --ch 1 --voltage 12.5 --current 2.0
  python cli.py --port COM35 enable --ch 1
  python cli.py --port COM35 disable --ch 2
  python cli.py --port COM35 log --output data.csv --interval 0.5
  python cli.py serve --port COM35 --host 0.0.0.0 --http-port 8080
"""

import csv
import sys
import time
from datetime import datetime

import click

from ps2000b import PS2000B, ChannelStatus, list_serial_ports, find_ps2000b
from ps2000b.device import PS2000BError


# ── Shared options ──────────────────────────────────────────────────────────

def _port_option(required=True):
    return click.option(
        "--port", "-p",
        default=None,
        show_default=True,
        required=required,
        help="Serial port (e.g. COM35 or /dev/ttyUSB0). Auto-detected if omitted.",
    )


def _resolve_port(port: str | None) -> str:
    if port:
        return port
    detected = find_ps2000b()
    if detected:
        click.echo(f"Auto-detected PS2000B on {detected}")
        return detected
    available = list_serial_ports()
    if available:
        click.echo(f"Available ports: {', '.join(available)}", err=True)
    raise click.UsageError("Could not auto-detect PS2000B. Use --port to specify.")


# ── CLI root ────────────────────────────────────────────────────────────────

@click.group()
def cli():
    """Control and monitor the EA Elektro-Automatik PS2000B power supply."""


# ── ports ───────────────────────────────────────────────────────────────────

@cli.command()
def ports():
    """List available serial ports on this machine."""
    available = list_serial_ports()
    if not available:
        click.echo("No serial ports found.")
        return
    detected = find_ps2000b()
    for p in available:
        marker = "  ← PS2000B detected" if p == detected else ""
        click.echo(f"  {p}{marker}")


# ── status ──────────────────────────────────────────────────────────────────

@cli.command()
@_port_option(required=False)
def status(port):
    """Read and print current voltage and current from both channels."""
    port = _resolve_port(port)
    try:
        with PS2000B(port) as psu:
            channels = psu.get_all()
    except PS2000BError as e:
        raise click.ClickException(str(e))

    click.echo(f"\nPS2000B on {port}")
    click.echo("-" * 40)
    for ch in channels:
        state = "ON " if ch.output_on else "OFF"
        click.echo(
            f"  CH{ch.channel + 1}  [{state}]  "
            f"{ch.voltage:6.3f} V   {ch.current:6.4f} A"
        )
    click.echo()


# ── set ─────────────────────────────────────────────────────────────────────

@cli.command()
@_port_option(required=False)
@click.option("--ch", type=click.IntRange(1, 2), required=True, help="Channel number (1 or 2)")
@click.option("--voltage", "-v", type=float, required=True, help="Setpoint voltage in Volts")
@click.option("--current", "-c", type=float, required=True, help="Setpoint current in Amps")
def set(port, ch, voltage, current):
    """Set the voltage and current setpoints for a channel."""
    port = _resolve_port(port)
    channel = ch - 1   # convert to 0-based
    try:
        with PS2000B(port) as psu:
            psu.set_output(channel, voltage, current)
            # Read back to confirm
            result = psu.get_status(channel)
    except PS2000BError as e:
        raise click.ClickException(str(e))

    click.echo(f"CH{ch} setpoints applied.")
    click.echo(f"  Actual reading: {result.voltage:.3f} V  {result.current:.4f} A")


# ── enable / disable ────────────────────────────────────────────────────────

@cli.command()
@_port_option(required=False)
@click.option("--ch", type=click.IntRange(1, 2), required=True, help="Channel number (1 or 2)")
def enable(port, ch):
    """Enable (switch on) a channel output."""
    port = _resolve_port(port)
    try:
        with PS2000B(port) as psu:
            psu.enable_output(ch - 1, True)
    except PS2000BError as e:
        raise click.ClickException(str(e))
    click.echo(f"CH{ch} output enabled.")


@cli.command()
@_port_option(required=False)
@click.option("--ch", type=click.IntRange(1, 2), required=True, help="Channel number (1 or 2)")
def disable(port, ch):
    """Disable (switch off) a channel output."""
    port = _resolve_port(port)
    try:
        with PS2000B(port) as psu:
            psu.enable_output(ch - 1, False)
    except PS2000BError as e:
        raise click.ClickException(str(e))
    click.echo(f"CH{ch} output disabled.")


# ── log ─────────────────────────────────────────────────────────────────────

@cli.command()
@_port_option(required=False)
@click.option("--output", "-o", default=None, help="CSV output file (default: YYYY-MM-DD.csv)")
@click.option("--interval", "-i", default=0.5, show_default=True, help="Sample interval in seconds")
def log(port, output, interval):
    """Continuously log both channels to CSV. Press Ctrl-C to stop."""
    port = _resolve_port(port)
    if output is None:
        output = datetime.now().strftime("%Y-%m-%d") + ".csv"

    click.echo(f"Logging to {output}  (Ctrl-C to stop)")

    fieldnames = ["timestamp", "ch1_voltage", "ch1_current", "ch1_on", "ch2_voltage", "ch2_current", "ch2_on"]

    try:
        with PS2000B(port) as psu, open(output, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if f.tell() == 0:
                writer.writeheader()

            while True:
                try:
                    channels = psu.get_all()
                except PS2000BError as e:
                    click.echo(f"  Read error: {e} — reconnecting...", err=True)
                    psu.reconnect()
                    time.sleep(1.0)
                    continue

                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                row = {
                    "timestamp":   ts,
                    "ch1_voltage": channels[0].voltage,
                    "ch1_current": channels[0].current,
                    "ch1_on":      channels[0].output_on,
                    "ch2_voltage": channels[1].voltage,
                    "ch2_current": channels[1].current,
                    "ch2_on":      channels[1].output_on,
                }
                writer.writerow(row)
                f.flush()

                click.echo(
                    f"  {ts}  "
                    f"CH1: {channels[0].voltage:6.3f}V {channels[0].current:6.4f}A  "
                    f"CH2: {channels[1].voltage:6.3f}V {channels[1].current:6.4f}A"
                )
                time.sleep(interval)

    except KeyboardInterrupt:
        click.echo(f"\nLogging stopped. File saved: {output}")


# ── serve ────────────────────────────────────────────────────────────────────

@cli.command()
@_port_option(required=False)
@click.option("--host", default="0.0.0.0", show_default=True, help="Bind host")
@click.option("--http-port", default=8080, show_default=True, help="HTTP port")
@click.option("--reload", is_flag=True, default=False, help="Enable auto-reload (dev only)")
@click.option("--log-file", default=None, help="Auto-start CSV logging to this file on startup")
@click.option("--log-interval", default=1.0, show_default=True, help="Log sample interval in seconds")
def serve(port, host, http_port, reload, log_file, log_interval):
    """Start the web dashboard server."""
    port = _resolve_port(port)
    try:
        import uvicorn
    except ImportError:
        raise click.ClickException("uvicorn is not installed. Run: pip install uvicorn[standard]")

    click.echo(f"Starting PS2000B dashboard on http://{host}:{http_port}")
    click.echo(f"  Serial port: {port}")
    if log_file:
        click.echo(f"  Auto-logging to {log_file} every {log_interval}s")
    click.echo(f"  Open http://localhost:{http_port} in your browser\n")

    import os
    os.environ["PS2000B_PORT"] = port
    os.environ["PS2000B_SERVER_URL"] = f"http://127.0.0.1:{http_port}"
    if log_file:
        os.environ["PS2000B_LOG_FILE"] = log_file
        os.environ["PS2000B_LOG_INTERVAL"] = str(log_interval)

    uvicorn.run(
        "server.main:app",
        host=host,
        port=http_port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    cli()
