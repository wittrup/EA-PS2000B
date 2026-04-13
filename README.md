# EA-PS2000B

Cross-platform controller for the **Elektro Automatik PS 2000 B** dual-channel power supply.

Reads and controls both channels (voltage, current, output on/off) over RS-232/USB.
Includes a web dashboard with live charts and an integrated CSV logger.

## Quick start

```bash
cd ps2000b-control
pip install -r requirements.txt
python cli.py serve --port COM6 --http-port 8080
# then open http://localhost:8080
```

See [`ps2000b-control/README.md`](ps2000b-control/README.md) for full documentation.
