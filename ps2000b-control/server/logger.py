"""
Background CSV logger for the PS2000B server.

Runs in its own thread alongside the FastAPI server, sharing the same
device connection (protected by the device's threading.Lock).

Logs: timestamp, both channels actual V/A/on, both channels setpoint V/A.
"""

import csv
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from ps2000b import PS2000B


@dataclass
class LogStatus:
    running:    bool    = False
    filename:   str     = ""
    samples:    int     = 0
    started_at: float   = 0.0
    error:      str     = ""

    def as_dict(self) -> dict:
        return {
            "running":    self.running,
            "filename":   self.filename,
            "samples":    self.samples,
            "started_at": self.started_at,
            "error":      self.error,
        }


FIELDNAMES = [
    "timestamp",
    "ch1_voltage", "ch1_current", "ch1_on",
    "ch1_v_set",   "ch1_a_set",
    "ch2_voltage", "ch2_current", "ch2_on",
    "ch2_v_set",   "ch2_a_set",
]


class DeviceLogger:
    def __init__(self):
        self._device: Optional[PS2000B] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._status = LogStatus()
        self._lock = threading.Lock()       # protects status fields

    def set_device(self, device: PS2000B) -> None:
        self._device = device

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self, filename: Optional[str] = None, interval: float = 1.0) -> LogStatus:
        with self._lock:
            if self._status.running:
                return self._status

            if filename is None:
                filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".csv"

            self._stop_event.clear()
            self._status = LogStatus(
                running    = True,
                filename   = filename,
                samples    = 0,
                started_at = time.time(),
            )

        self._thread = threading.Thread(
            target  = self._run,
            args    = (filename, interval),
            daemon  = True,
            name    = "ps2000b-logger",
        )
        self._thread.start()
        return self.status

    def stop(self) -> LogStatus:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        with self._lock:
            self._status.running = False
        return self.status

    @property
    def status(self) -> LogStatus:
        with self._lock:
            # Return a copy so the caller can't mutate internal state
            return LogStatus(**self._status.__dict__)

    def file_path(self) -> Optional[Path]:
        with self._lock:
            fn = self._status.filename
        return Path(fn) if fn else None

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run(self, filename: str, interval: float) -> None:
        path = Path(filename)
        write_header = not path.exists() or path.stat().st_size == 0

        try:
            with open(path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                if write_header:
                    writer.writeheader()

                while not self._stop_event.is_set():
                    row = self._sample()
                    if row:
                        writer.writerow(row)
                        f.flush()
                        with self._lock:
                            self._status.samples += 1
                    self._stop_event.wait(interval)

        except Exception as e:
            with self._lock:
                self._status.error   = str(e)
                self._status.running = False

    def _sample(self) -> Optional[dict]:
        if self._device is None or not self._device.is_open:
            return None
        try:
            actuals   = self._device.get_all()
            setpoints = self._device.get_all_setpoints()
        except Exception:
            return None

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        a1, a2 = actuals[0], actuals[1]
        s1, s2 = setpoints[0], setpoints[1]
        return {
            "timestamp":  ts,
            "ch1_voltage": a1.voltage,  "ch1_current": a1.current,  "ch1_on": int(a1.output_on),
            "ch1_v_set":   s1["voltage"], "ch1_a_set":   s1["current"],
            "ch2_voltage": a2.voltage,  "ch2_current": a2.current,  "ch2_on": int(a2.output_on),
            "ch2_v_set":   s2["voltage"], "ch2_a_set":   s2["current"],
        }


# Module-level singleton shared by api.py and main.py
device_logger = DeviceLogger()
