"use strict";

// ── Config ───────────────────────────────────────────────────────────────────
const MAX_POINTS    = 120;   // 24 s of history at 200 ms/point
const WS_RETRY_MS   = 2000;  // reconnect delay
const CHART_VOLT    = "#f59e0b";
const CHART_AMP     = "#3b82f6";
const CHART_GRID    = "#2a3045";
const CHART_TICK    = "#64748b";

// ── State ────────────────────────────────────────────────────────────────
const state = {
  ch1: { output_on: false, vSet: 0, aSet: 0 },
  ch2: { output_on: false, vSet: 0, aSet: 0 },
  deviceOffline: false,
};

// ── Chart factory ─────────────────────────────────────────────────────────────
function makeChart(canvasId) {
  const labels = Array(MAX_POINTS).fill("");
  const vData  = Array(MAX_POINTS).fill(null);
  const aData  = Array(MAX_POINTS).fill(null);

  const ctx = document.getElementById(canvasId).getContext("2d");
  return new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Voltage (V)",
          data: vData,
          borderColor: CHART_VOLT,
          backgroundColor: CHART_VOLT + "22",
          borderWidth: 1.5,
          pointRadius: 0,
          fill: true,
          yAxisID: "yV",
          tension: 0.3,
        },
        {
          label: "Current (A)",
          data: aData,
          borderColor: CHART_AMP,
          backgroundColor: CHART_AMP + "22",
          borderWidth: 1.5,
          pointRadius: 0,
          fill: true,
          yAxisID: "yA",
          tension: 0.3,
        },
      ],
    },
    options: {
      animation: false,
      responsive: true,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          labels: { color: CHART_TICK, boxWidth: 12, font: { size: 11 } },
        },
        tooltip: { enabled: true },
      },
      scales: {
        x: { display: false },
        yV: {
          type: "linear",
          position: "left",
          min: 0,
          max: 42,
          ticks: { color: CHART_VOLT, font: { size: 10 } },
          grid: { color: CHART_GRID },
        },
        yA: {
          type: "linear",
          position: "right",
          min: 0,
          max: 6,
          ticks: { color: CHART_AMP, font: { size: 10 } },
          grid: { drawOnChartArea: false },
        },
      },
    },
  });
}

// ── DOM helpers ──────────────────────────────────────────────────────────────
function el(id) { return document.getElementById(id); }

function updateReading(prefix, voltage, current) {
  el(`${prefix}-v`).textContent = voltage.toFixed(3);
  el(`${prefix}-a`).textContent = current.toFixed(4);
}

function updateToggleButton(btn, isOn) {
  btn.textContent = isOn ? "ON" : "OFF";
  btn.classList.toggle("on", isOn);
}

function pushChartPoint(chart, voltage, current) {
  chart.data.datasets[0].data.push(voltage);
  chart.data.datasets[1].data.push(current);
  chart.data.labels.push("");
  if (chart.data.datasets[0].data.length > MAX_POINTS) {
    chart.data.datasets[0].data.shift();
    chart.data.datasets[1].data.shift();
    chart.data.labels.shift();
  }
  chart.update("none");
}

// ── Connection status ─────────────────────────────────────────────────────────
const connPill = el("conn-status");
function setConnStatus(s, text) {
  connPill.className = `status-pill ${s}`;
  connPill.textContent = text;
}

// ── WebSocket ─────────────────────────────────────────────────────────────────
const chart1 = makeChart("chart-ch1");
const chart2 = makeChart("chart-ch2");

function connect() {
  const wsUrl = `ws://${location.host}/ws`;
  setConnStatus("connecting", "Connecting…");
  const ws = new WebSocket(wsUrl);

  ws.onopen = () => setConnStatus("connected", `Connected · ${location.host}`);

  ws.onmessage = (evt) => {
    const msg = JSON.parse(evt.data);
    if (msg.error) {
      if (msg.device_offline) {
        setConnStatus("device-offline", "Device offline \u2014 reconnecting\u2026");
      } else {
        setConnStatus("disconnected", msg.error);
      }
      state.deviceOffline = true;
      return;
    }

    // Device just came back online — reload setpoints (device may have reset)
    if (state.deviceOffline) {
      state.deviceOffline = false;
      loadSetpoints();
    }

    setConnStatus("connected", `Connected \u00b7 ${location.host}`);

    const { ch1, ch2 } = msg;

    updateReading("ch1", ch1.voltage, ch1.current);
    updateReading("ch2", ch2.voltage, ch2.current);

    state.ch1.output_on = ch1.output_on;
    state.ch2.output_on = ch2.output_on;

    updateToggleButton(toggles[0], ch1.output_on);
    updateToggleButton(toggles[1], ch2.output_on);

    pushChartPoint(chart1, ch1.voltage, ch1.current);
    pushChartPoint(chart2, ch2.voltage, ch2.current);
  };

  ws.onclose = () => {
    setConnStatus("disconnected", "Disconnected — retrying…");
    setTimeout(connect, WS_RETRY_MS);
  };

  ws.onerror = () => ws.close();
}

// ── Output toggles ─────────────────────────────────────────────────────────────
const toggles = Array.from(document.querySelectorAll(".output-toggle"));

toggles.forEach((btn) => {
  btn.addEventListener("click", async () => {
    const ch  = parseInt(btn.dataset.ch, 10);
    const key = `ch${ch}`;
    const nowOn = !state[key].output_on;

    try {
      const res = await fetch(`/api/channel/${ch}/enable`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ enabled: nowOn }),
      });
      if (!res.ok) {
        const err = await res.json();
        console.error("Enable error:", err.detail);
      }
    } catch (e) {
      console.error("Network error:", e);
    }
  });
});

// ── Setpoint controls (slider + number input, bidirectionally synced) ─────────
async function sendSetpoint(ch, type, value) {
  const endpoint = type === "voltage" ? "set-voltage" : "set-current";
  const body     = type === "voltage" ? { voltage: value } : { current: value };
  try {
    const res = await fetch(`/api/channel/${ch}/${endpoint}`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json();
      console.error(`Set ${type} error:`, err.detail);
    }
  } catch (e) {
    console.error("Network error:", e);
  }
}

document.querySelectorAll(".setpoints input[type=range]").forEach((slider) => {
  const ch       = parseInt(slider.dataset.ch, 10);
  const type     = slider.dataset.type;
  const numInput = el(slider.id.replace("-set", "-out"));
  const decimals = type === "voltage" ? 1 : 2;

  // Slider dragging → update number input live
  slider.addEventListener("input", () => {
    numInput.value = parseFloat(slider.value).toFixed(decimals);
  });

  // Slider released → send to device
  slider.addEventListener("change", () => {
    const value = parseFloat(slider.value);
    numInput.value = value.toFixed(decimals);
    sendSetpoint(ch, type, value);
  });
});

document.querySelectorAll(".setpoint-num").forEach((numInput) => {
  const ch       = parseInt(numInput.dataset.ch, 10);
  const type     = numInput.dataset.type;
  const sliderId = numInput.id.replace("-out", "-set");
  const slider   = el(sliderId);
  const max      = parseFloat(numInput.max);
  const decimals = type === "voltage" ? 1 : 2;

  function commitValue() {
    let value = parseFloat(numInput.value);
    if (isNaN(value)) return;
    value = Math.max(0, Math.min(max, value));          // clamp to range
    numInput.value  = value.toFixed(decimals);
    slider.value    = value;
    sendSetpoint(ch, type, value);
  }

  // Enter or Tab commits
  numInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); commitValue(); numInput.blur(); }
    if (e.key === "Escape") { numInput.value = slider.value; numInput.blur(); }
  });

  // Focus-out also commits (click away / Tab away)
  numInput.addEventListener("blur", commitValue);

  // Select all text on focus for quick overtyping
  numInput.addEventListener("focus", () => numInput.select());
});

// ── Logging controls ──────────────────────────────────────────────────────────
const logToggleBtn    = el("log-toggle");
const logFilenameSpan = el("log-filename");
const logSamplesSpan  = el("log-samples");
const logDownloadLink = el("log-download");
const logIntervalInput = el("log-interval-input");

let logPollingTimer = null;

function applyLogStatus(s) {
  if (s.running) {
    logToggleBtn.textContent = "\u23F9 Stop Logging";
    logToggleBtn.className   = "log-btn log-stop";
    logFilenameSpan.textContent = s.filename || "";
    logSamplesSpan.textContent  = s.samples != null ? `${s.samples} samples` : "";
    logDownloadLink.style.display = s.filename ? "" : "none";
  } else {
    logToggleBtn.textContent = "\u25B6 Start Logging";
    logToggleBtn.className   = "log-btn log-start";
    if (!s.filename) {
      logFilenameSpan.textContent = "";
      logSamplesSpan.textContent  = "";
    } else {
      logFilenameSpan.textContent = s.filename;
      logSamplesSpan.textContent  = s.samples != null ? `${s.samples} samples` : "";
      logDownloadLink.style.display = "";
    }
    if (s.error) {
      logSamplesSpan.textContent = `Error: ${s.error}`;
    }
  }
}

async function pollLogStatus() {
  try {
    const res = await fetch("/api/log/status");
    if (res.ok) applyLogStatus(await res.json());
  } catch (_) { /* ignore */ }
}

function startLogPolling() {
  if (logPollingTimer) return;
  logPollingTimer = setInterval(pollLogStatus, 1000);
}

function stopLogPolling() {
  if (logPollingTimer) { clearInterval(logPollingTimer); logPollingTimer = null; }
}

logToggleBtn.addEventListener("click", async () => {
  const isRunning = logToggleBtn.classList.contains("log-stop");
  logToggleBtn.disabled = true;
  if (isRunning) {
    try {
      const res = await fetch("/api/log/stop", { method: "POST" });
      if (res.ok) { applyLogStatus(await res.json()); stopLogPolling(); }
      else { const e = await res.json(); logSamplesSpan.textContent = `Error: ${e.detail || res.status}`; }
    } catch (e) { logSamplesSpan.textContent = `Error: ${e.message}`; console.error("Log stop error:", e); }
  } else {
    const interval = parseFloat(logIntervalInput.value) || 1.0;
    try {
      const res = await fetch("/api/log/start", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ interval }),
      });
      if (res.ok) { applyLogStatus(await res.json()); startLogPolling(); }
      else { const e = await res.json(); logSamplesSpan.textContent = `Error: ${e.detail || res.status}`; }
    } catch (e) { logSamplesSpan.textContent = `Error: ${e.message}`; console.error("Log start error:", e); }
  }
  logToggleBtn.disabled = false;
});

// ── Init ──────────────────────────────────────────────────────────────────────
async function loadSetpoints() {
  try {
    const res  = await fetch("/api/setpoints");
    if (!res.ok) return;
    const data = await res.json();
    data.setpoints.forEach((sp) => {
      const ch = sp.channel + 1;
      const vSlider = el(`ch${ch}-v-set`);
      const aSlider = el(`ch${ch}-a-set`);
      const vNum    = el(`ch${ch}-v-out`);
      const aNum    = el(`ch${ch}-a-out`);
      vSlider.value = sp.voltage;
      aSlider.value = sp.current;
      vNum.value    = sp.voltage.toFixed(1);
      aNum.value    = sp.current.toFixed(2);
    });
  } catch (e) {
    console.warn("Could not load setpoints:", e);
  }
}

async function initLogStatus() {
  try {
    const res = await fetch("/api/log/status");
    if (res.ok) {
      const s = await res.json();
      applyLogStatus(s);
      if (s.running) startLogPolling();
    }
  } catch (_) { /* no device yet */ }
}

loadSetpoints();
initLogStatus();
connect();
