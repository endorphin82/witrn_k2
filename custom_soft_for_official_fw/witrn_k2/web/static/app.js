/**
 * WITRN K2 Laboratory Web Dashboard Client
 */

// App State
const state = {
  ws: null,
  connected: false,
  mode: "hardware",
  recording: false,
  paused: false,
  recStartTime: null,
  recDuration: 0,
  recPointCount: 0,
  sampleRate: 10,

  // Selected time window in seconds (0 = All)
  timeWindow: 30,

  // Channel toggles
  channels: {
    voltage: true,
    current: true,
    power: true,
    resistance: false,
    dpdn: false,
    temp: false,
  },

  // Samples buffer
  samples: [],
  maxSamples: 15000,

  // Hover crosshair info
  hoverIndex: null,
};

// Colors
const COLORS = {
  voltage: "#00e5ff",
  current: "#00e676",
  power: "#ffb300",
  resistance: "#b388ff",
  dp: "#60a5fa",
  dn: "#93c5fd",
  temp_in: "#ff4081",
  temp_out: "#f43f5e",
  grid: "#1c2438",
  text: "#64748b",
};

// DOM Elements
const el = {
  deviceBadge: document.getElementById("deviceBadge"),
  statusIndicator: document.getElementById("statusIndicator"),
  deviceLabel: document.getElementById("deviceLabel"),
  modeName: document.getElementById("modeName"),
  btnModeToggle: document.getElementById("btnModeToggle"),
  btnReconnect: document.getElementById("btnReconnect"),

  valVoltage: document.getElementById("valVoltage"),
  minVoltage: document.getElementById("minVoltage"),
  maxVoltage: document.getElementById("maxVoltage"),
  vppVoltage: document.getElementById("vppVoltage"),

  valCurrent: document.getElementById("valCurrent"),
  minCurrent: document.getElementById("minCurrent"),
  maxCurrent: document.getElementById("maxCurrent"),
  ippCurrent: document.getElementById("ippCurrent"),

  valPower: document.getElementById("valPower"),
  minPower: document.getElementById("minPower"),
  maxPower: document.getElementById("maxPower"),

  valResistance: document.getElementById("valResistance"),
  valDp: document.getElementById("valDp"),
  valDn: document.getElementById("valDn"),

  valCapacity: document.getElementById("valCapacity"),
  valEnergy: document.getElementById("valEnergy"),
  valK2RecTime: document.getElementById("valK2RecTime"),
  valK2Uptime: document.getElementById("valK2Uptime"),

  valTempIn: document.getElementById("valTempIn"),
  valTempOut: document.getElementById("valTempOut"),
  valGroup: document.getElementById("valGroup"),

  // Rec controls
  recBadge: document.getElementById("recBadge"),
  recStatusText: document.getElementById("recStatusText"),
  recInfoBlock: document.getElementById("recInfoBlock"),
  recTimer: document.getElementById("recTimer"),
  recPointCount: document.getElementById("recPointCount"),
  btnRecordStart: document.getElementById("btnRecordStart"),
  btnRecordPause: document.getElementById("btnRecordPause"),
  btnRecordResume: document.getElementById("btnRecordResume"),
  btnRecordStop: document.getElementById("btnRecordStop"),
  sampleRateSelect: document.getElementById("sampleRateSelect"),
  btnClearChart: document.getElementById("btnClearChart"),

  // Chart
  canvas: document.getElementById("telemetryChart"),
  chartHoverInfo: document.getElementById("chartHoverInfo"),

  // Tabs
  tabButtons: document.querySelectorAll(".tab-btn"),
  tabContents: document.querySelectorAll(".tab-content"),
  statsTableBody: document.getElementById("statsTableBody"),
  statMahForward: document.getElementById("statMahForward"),
  statMahReverse: document.getElementById("statMahReverse"),
  statMahNet: document.getElementById("statMahNet"),
  statMwhForward: document.getElementById("statMwhForward"),
  statMwhReverse: document.getElementById("statMwhReverse"),
  statMwhNet: document.getElementById("statMwhNet"),
  statDuration: document.getElementById("statDuration"),
  sessionsTableBody: document.getElementById("sessionsTableBody"),
  btnRefreshSessions: document.getElementById("btnRefreshSessions"),
  dropZone: document.getElementById("dropZone"),
  fileInput: document.getElementById("fileInput"),
  importStatus: document.getElementById("importStatus"),
  systemDiagnostics: document.getElementById("systemDiagnostics"),

  // Auto-stop modal
  autoStopModal: document.getElementById("autoStopModal"),
  btnAutoStopModal: document.getElementById("btnAutoStopModal"),
  btnCloseAutoStop: document.getElementById("btnCloseAutoStop"),
  btnSaveAutoStop: document.getElementById("btnSaveAutoStop"),
  autoStopEnabled: document.getElementById("autoStopEnabled"),
  autoStopKind: document.getElementById("autoStopKind"),
  autoStopThreshold: document.getElementById("autoStopThreshold"),
  autoStopDuration: document.getElementById("autoStopDuration"),
  autoStopUnit: document.getElementById("autoStopUnit"),
};

// Canvas context
const ctx = el.canvas.getContext("2d");

// Initialize WebSocket connection
function initWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  state.ws = new WebSocket(wsUrl);

  state.ws.onopen = () => {
    console.log("WebSocket connected");
  };

  state.ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleWsMessage(data);
    } catch (e) {
      console.error("WS Parse error", e);
    }
  };

  state.ws.onclose = () => {
    console.warn("WebSocket disconnected, reconnecting in 2s...");
    updateDeviceBadge(false, "Відключено від сервера");
    setTimeout(initWebSocket, 2000);
  };
}

function handleWsMessage(msg) {
  if (msg.type === "init") {
    handleDeviceState(msg.device);
    handleRecorderStatus(msg.recorder);
  } else if (msg.type === "telemetry") {
    if (msg.latest) {
      updateDigitalReadouts(msg.latest);
    }
    if (msg.batch) {
      for (const s of msg.batch) {
        pushSample(s);
      }
    } else if (msg.latest) {
      pushSample(msg.latest);
    }
    if (msg.recorder) {
      handleRecorderStatus(msg.recorder);
    }
    scheduleChartRender();
  } else if (msg.type === "event" && msg.event === "auto_stop") {
    alert(msg.message);
  }
}

function pushSample(sample) {
  state.samples.push(sample);
  if (state.samples.length > state.maxSamples) {
    state.samples.shift();
  }
}

function handleDeviceState(dev) {
  state.mode = dev.mode || "hardware";
  el.modeName.textContent = state.mode === "simulator" ? "Симулятор" : "USB HID";

  if (dev.connected) {
    const name = dev.info ? dev.info.name : "WITRN K2";
    const path = dev.info ? dev.info.path : "";
    updateDeviceBadge(true, `${name} (${path})`, state.mode === "simulator");
  } else {
    updateDeviceBadge(false, dev.error || "Тестер K2 не підключено");
  }
}

function updateDeviceBadge(online, text, isSimulator = false) {
  el.statusIndicator.className = "status-indicator " + (online ? (isSimulator ? "simulator" : "online") : "offline");
  el.deviceLabel.textContent = text;
}

function handleRecorderStatus(rec) {
  state.recording = rec.is_recording;
  state.paused = rec.is_paused;
  state.recPointCount = rec.count || 0;

  if (state.recording) {
    el.recBadge.className = "rec-status-indicator recording";
    el.recStatusText.textContent = state.paused ? "ЗАПИС ПРИЗУПИНЕНО" : "ТРИВАЄ ЗАПИС...";
    el.recInfoBlock.style.display = "flex";
    el.recPointCount.textContent = state.recPointCount;

    el.btnRecordStart.style.display = "none";
    el.btnRecordPause.style.display = state.paused ? "none" : "inline-block";
    el.btnRecordResume.style.display = state.paused ? "inline-block" : "none";
    el.btnRecordStop.style.display = "inline-block";
  } else {
    el.recBadge.className = "rec-status-indicator";
    el.recStatusText.textContent = "ГОТОВИЙ ДО ЗАПИСУ";
    el.recInfoBlock.style.display = "none";

    el.btnRecordStart.style.display = "inline-block";
    el.btnRecordPause.style.display = "none";
    el.btnRecordResume.style.display = "none";
    el.btnRecordStop.style.display = "none";
  }
}

// Update Big Digital Meters
function updateDigitalReadouts(s) {
  el.valVoltage.textContent = s.voltage.toFixed(4);
  el.valCurrent.textContent = s.current.toFixed(4);
  el.valPower.textContent = s.power.toFixed(4);

  el.valResistance.textContent = s.resistance !== null ? `${s.resistance.toFixed(2)} Ω` : "---";
  el.valDp.textContent = s.dp !== null ? s.dp.toFixed(3) : "0.00";
  el.valDn.textContent = s.dn !== null ? s.dn.toFixed(3) : "0.00";

  el.valCapacity.textContent = s.ah !== null ? s.ah.toFixed(4) : "0.0000";
  el.valEnergy.textContent = s.wh !== null ? s.wh.toFixed(4) : "0.0000";

  el.valK2RecTime.textContent = s.record_seconds || 0;
  el.valK2Uptime.textContent = s.uptime || 0;
  el.valGroup.textContent = s.group || 1;

  el.valTempIn.textContent = s.temp_in !== null ? s.temp_in.toFixed(1) : "--.-";
  el.valTempOut.textContent = s.temp_out !== null ? s.temp_out.toFixed(1) : "--.-";
}

// Chart Rendering Engine
let animFrameRequested = false;

function scheduleChartRender() {
  if (!animFrameRequested) {
    animFrameRequested = true;
    requestAnimationFrame(renderChart);
  }
}

function resizeCanvas() {
  const dpr = window.devicePixelRatio || 1;
  const rect = el.canvas.getBoundingClientRect();
  el.canvas.width = rect.width * dpr;
  el.canvas.height = rect.height * dpr;
  // setTransform (not scale) — scale accumulates on every resize and breaks drawing
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  scheduleChartRender();
}

window.addEventListener("resize", resizeCanvas);

function renderChart() {
  animFrameRequested = false;
  const dpr = window.devicePixelRatio || 1;
  const w = el.canvas.width / dpr;
  const h = el.canvas.height / dpr;

  ctx.clearRect(0, 0, w, h);

  if (state.samples.length < 2) {
    ctx.fillStyle = COLORS.text;
    ctx.font = "14px monospace";
    ctx.textAlign = "center";
    ctx.fillText("Очікування телеметрії від WITRN K2...", w / 2, h / 2);
    return;
  }

  // Filter samples by time window
  const latestTime = state.samples[state.samples.length - 1].time;
  const minTime = state.timeWindow > 0 ? latestTime - state.timeWindow : state.samples[0].time;

  const visible = state.samples.filter((s) => s.time >= minTime);
  if (visible.length < 2) return;

  // Determine scale ranges
  let minV = Infinity, maxV = -Infinity;
  let minI = Infinity, maxI = -Infinity;
  let minP = Infinity, maxP = -Infinity;

  for (const s of visible) {
    if (s.voltage < minV) minV = s.voltage;
    if (s.voltage > maxV) maxV = s.voltage;
    if (s.current < minI) minI = s.current;
    if (s.current > maxI) maxI = s.current;
    if (s.power < minP) minP = s.power;
    if (s.power > maxP) maxP = s.power;
  }

  // Update min/max/vpp in header metrics
  el.minVoltage.textContent = minV.toFixed(3);
  el.maxVoltage.textContent = maxV.toFixed(3);
  el.vppVoltage.textContent = Math.max(0, maxV - minV).toFixed(3);

  el.minCurrent.textContent = minI.toFixed(3);
  el.maxCurrent.textContent = maxI.toFixed(3);
  el.ippCurrent.textContent = Math.max(0, maxI - minI).toFixed(3);

  el.minPower.textContent = minP.toFixed(3);
  el.maxPower.textContent = maxP.toFixed(3);

  // Padding
  const padLeft = 55;
  const padRight = 55;
  const padTop = 20;
  const padBottom = 25;
  const plotW = w - padLeft - padRight;
  const plotH = h - padTop - padBottom;

  // Helper map functions
  const tMin = visible[0].time;
  const tMax = visible[visible.length - 1].time;
  const tSpan = Math.max(0.001, tMax - tMin);

  function mapX(t) {
    return padLeft + ((t - tMin) / tSpan) * plotW;
  }

  // Auto-range voltage (Left Axis)
  const vSpan = Math.max(0.5, (maxV - minV) * 1.15);
  const vMid = (maxV + minV) / 2;
  const vLo = Math.max(0, vMid - vSpan / 2);
  const vHi = vMid + vSpan / 2;

  function mapYVoltage(v) {
    return padTop + plotH - ((v - vLo) / (vHi - vLo)) * plotH;
  }

  // Auto-range current (Right Axis)
  const iSpan = Math.max(0.1, (maxI - minI) * 1.15);
  const iMid = (maxI + minI) / 2;
  const iLo = iMid - iSpan / 2;
  const iHi = iMid + iSpan / 2;

  function mapYCurrent(i) {
    return padTop + plotH - ((i - iLo) / (iHi - iLo)) * plotH;
  }

  // Draw Grid
  ctx.strokeStyle = COLORS.grid;
  ctx.lineWidth = 1;
  const gridSteps = 5;

  ctx.fillStyle = COLORS.text;
  ctx.font = "11px monospace";
  ctx.textAlign = "right";

  for (let g = 0; g <= gridSteps; g++) {
    const gy = padTop + (plotH / gridSteps) * g;
    ctx.beginPath();
    ctx.moveTo(padLeft, gy);
    ctx.lineTo(w - padRight, gy);
    ctx.stroke();

    // Voltage label (left)
    const valV = vHi - ((vHi - vLo) / gridSteps) * g;
    ctx.fillStyle = COLORS.voltage;
    ctx.fillText(`${valV.toFixed(2)}V`, padLeft - 6, gy + 3);

    // Current label (right)
    const valI = iHi - ((iHi - iLo) / gridSteps) * g;
    ctx.fillStyle = COLORS.current;
    ctx.textAlign = "left";
    ctx.fillText(`${valI.toFixed(2)}A`, w - padRight + 6, gy + 3);
    ctx.textAlign = "right";
  }

  // Time axis labels
  ctx.fillStyle = COLORS.text;
  ctx.textAlign = "center";
  for (let step = 0; step <= 4; step++) {
    const gx = padLeft + (plotW / 4) * step;
    const timeVal = tMin + (tSpan / 4) * step;
    ctx.fillText(`${timeVal.toFixed(1)}s`, gx, h - 8);
  }

  // Helper to draw series
  function drawSeries(color, mapYFn, key) {
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    let started = false;

    for (let idx = 0; idx < visible.length; idx++) {
      const s = visible[idx];
      const val = s[key];
      if (val === null || val === undefined) continue;

      const px = mapX(s.time);
      const py = mapYFn(val);

      if (!started) {
        ctx.moveTo(px, py);
        started = true;
      } else {
        ctx.lineTo(px, py);
      }
    }
    ctx.stroke();
  }

  // Draw active channels
  if (state.channels.voltage) {
    drawSeries(COLORS.voltage, mapYVoltage, "voltage");
  }
  if (state.channels.current) {
    drawSeries(COLORS.current, mapYCurrent, "current");
  }
  if (state.channels.power) {
    // Power mapped to voltage scale proportional
    drawSeries(COLORS.power, mapYVoltage, "power");
  }
  if (state.channels.temp) {
    drawSeries(COLORS.temp_in, (t) => padTop + plotH - (t / 80) * plotH, "temp_in");
  }
  if (state.channels.dpdn) {
    drawSeries(COLORS.dp, (d) => padTop + plotH - (d / 5.0) * plotH, "dp");
    drawSeries(COLORS.dn, (d) => padTop + plotH - (d / 5.0) * plotH, "dn");
  }

  // Draw Crosshair on mouse hover
  if (state.hoverIndex !== null && state.hoverIndex < visible.length) {
    const hs = visible[state.hoverIndex];
    const hx = mapX(hs.time);

    ctx.strokeStyle = "rgba(255, 255, 255, 0.4)";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(hx, padTop);
    ctx.lineTo(hx, padTop + plotH);
    ctx.stroke();
    ctx.setLineDash([]);
  }
}

// Canvas Mouse Interactions
el.canvas.addEventListener("mousemove", (e) => {
  const dpr = window.devicePixelRatio || 1;
  const rect = el.canvas.getBoundingClientRect();
  const mx = (e.clientX - rect.left);

  const padLeft = 55;
  const padRight = 55;
  const plotW = (el.canvas.width / dpr) - padLeft - padRight;

  if (mx < padLeft || mx > padLeft + plotW || state.samples.length === 0) {
    state.hoverIndex = null;
    el.chartHoverInfo.style.display = "none";
    scheduleChartRender();
    return;
  }

  const latestTime = state.samples[state.samples.length - 1].time;
  const minTime = state.timeWindow > 0 ? latestTime - state.timeWindow : state.samples[0].time;
  const visible = state.samples.filter((s) => s.time >= minTime);
  if (visible.length === 0) return;

  const tFrac = (mx - padLeft) / plotW;
  const targetTime = visible[0].time + tFrac * (visible[visible.length - 1].time - visible[0].time);

  // Binary search nearest sample
  let bestIdx = 0;
  let minDiff = Infinity;
  for (let i = 0; i < visible.length; i++) {
    const diff = Math.abs(visible[i].time - targetTime);
    if (diff < minDiff) {
      minDiff = diff;
      bestIdx = i;
    }
  }

  state.hoverIndex = bestIdx;
  const s = visible[bestIdx];

  el.chartHoverInfo.style.display = "block";
  el.chartHoverInfo.innerHTML = `
    <strong>Час: ${s.time.toFixed(2)} с</strong><br>
    V: <span style="color:${COLORS.voltage}">${s.voltage.toFixed(4)} V</span> |
    I: <span style="color:${COLORS.current}">${s.current.toFixed(4)} A</span> |
    P: <span style="color:${COLORS.power}">${s.power.toFixed(4)} W</span>
  `;

  scheduleChartRender();
});

el.canvas.addEventListener("mouseleave", () => {
  state.hoverIndex = null;
  el.chartHoverInfo.style.display = "none";
  scheduleChartRender();
});

// Controls & Buttons Events
el.btnRecordStart.addEventListener("click", async () => {
  const sessionName = prompt("Введіть назву сесії (або залиште порожнім для автоназви):", "");
  if (sessionName === null) return;

  const rate = parseInt(el.sampleRateSelect.value, 10);
  try {
    const res = await fetch("/api/record/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_name: sessionName || null,
        rate: rate,
        auto_stop_enabled: el.autoStopEnabled.checked,
        auto_stop_kind: el.autoStopKind.value,
        auto_stop_threshold: parseFloat(el.autoStopThreshold.value) || 0.05,
        auto_stop_duration: parseFloat(el.autoStopDuration.value) || 10,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);
    state.recStartTime = Date.now();
  } catch (err) {
    alert(`Помилка запуску запису: ${err.message}`);
  }
});

el.btnRecordPause.addEventListener("click", async () => {
  await fetch("/api/record/pause", { method: "POST" });
});

el.btnRecordResume.addEventListener("click", async () => {
  await fetch("/api/record/resume", { method: "POST" });
});

el.btnRecordStop.addEventListener("click", async () => {
  try {
    const res = await fetch("/api/record/stop", { method: "POST" });
    const data = await res.json();
    alert(`Запис зупинено та збережено у файл:\n${data.file}`);
    loadSessions();
  } catch (err) {
    alert(`Помилка: ${err.message}`);
  }
});

function clearChart() {
  state.samples = [];
  state.hoverIndex = null;
  el.chartHoverInfo.style.display = "none";
  scheduleChartRender();
}

el.btnClearChart.addEventListener("click", clearChart);

// Ctrl+Delete — same shortcut as the native GUI
window.addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.key === "Delete") {
    e.preventDefault();
    clearChart();
  }
});

el.btnModeToggle.addEventListener("click", async () => {
  const nextMode = state.mode === "hardware" ? "simulator" : "hardware";
  await fetch("/api/connect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode: nextMode }),
  });
});

el.btnReconnect.addEventListener("click", async () => {
  await fetch("/api/connect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode: state.mode }),
  });
});

// Time Window Buttons
document.querySelectorAll(".zoom-controls button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".zoom-controls button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    state.timeWindow = parseInt(btn.dataset.window, 10);
    scheduleChartRender();
  });
});

// Channel Checkbox Toggles
document.getElementById("chkVoltage").addEventListener("change", (e) => {
  state.channels.voltage = e.target.checked;
  scheduleChartRender();
});
document.getElementById("chkCurrent").addEventListener("change", (e) => {
  state.channels.current = e.target.checked;
  scheduleChartRender();
});
document.getElementById("chkPower").addEventListener("change", (e) => {
  state.channels.power = e.target.checked;
  scheduleChartRender();
});
document.getElementById("chkResistance").addEventListener("change", (e) => {
  state.channels.resistance = e.target.checked;
  scheduleChartRender();
});
document.getElementById("chkDpDn").addEventListener("change", (e) => {
  state.channels.dpdn = e.target.checked;
  scheduleChartRender();
});
document.getElementById("chkTemp").addEventListener("change", (e) => {
  state.channels.temp = e.target.checked;
  scheduleChartRender();
});

// Tab Switcher
el.tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    el.tabButtons.forEach((b) => b.classList.remove("active"));
    el.tabContents.forEach((c) => c.classList.remove("active"));

    btn.classList.add("active");
    const target = document.getElementById(btn.dataset.tab);
    if (target) target.classList.add("active");

    if (btn.dataset.tab === "tab-stats") {
      updateStatsTab();
    } else if (btn.dataset.tab === "tab-sessions") {
      loadSessions();
    } else if (btn.dataset.tab === "tab-info") {
      loadDiagnostics();
    }
  });
});

// Auto-Stop Modal
el.btnAutoStopModal.addEventListener("click", () => {
  el.autoStopModal.style.display = "flex";
});
el.btnCloseAutoStop.addEventListener("click", () => {
  el.autoStopModal.style.display = "none";
});
el.btnSaveAutoStop.addEventListener("click", () => {
  el.autoStopModal.style.display = "none";
});
el.autoStopKind.addEventListener("change", (e) => {
  el.autoStopUnit.textContent = e.target.value === "current" ? "A" : "W";
});

// Stats Calculation & Tab Rendering
function updateStatsTab() {
  if (state.samples.length === 0) return;

  const chs = [
    { name: "Напруга (VBUS)", key: "voltage", unit: "V" },
    { name: "Струм (IBUS)", key: "current", unit: "A" },
    { name: "Потужність", key: "power", unit: "W" },
    { name: "Опір", key: "resistance", unit: "Ω" },
    { name: "D+ Напруга", key: "dp", unit: "V" },
    { name: "D- Напруга", key: "dn", unit: "V" },
    { name: "Внутрішня темп.", key: "temp_in", unit: "°C" },
    { name: "Зовнішня темп.", key: "temp_out", unit: "°C" },
  ];

  let html = "";
  for (const c of chs) {
    const vals = state.samples.map((s) => s[c.key]).filter((v) => v !== null && isFinite(v));
    if (vals.length === 0) continue;

    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
    const vpp = max - min;

    html += `
      <tr>
        <td><strong>${c.name}</strong></td>
        <td>${min.toFixed(4)} ${c.unit}</td>
        <td>${max.toFixed(4)} ${c.unit}</td>
        <td>${avg.toFixed(4)} ${c.unit}</td>
        <td>${vpp.toFixed(4)} ${c.unit}</td>
      </tr>
    `;
  }
  el.statsTableBody.innerHTML = html;

  // Compute energy integration
  let ahPos = 0, ahNeg = 0, whPos = 0, whNeg = 0;
  for (let i = 1; i < state.samples.length; i++) {
    const p = state.samples[i - 1];
    const s = state.samples[i];
    const dt = s.time - p.time;
    if (dt > 0 && dt <= 2.0) {
      const avgI = (p.current + s.current) / 2.0;
      if (avgI >= 0) ahPos += (avgI * dt) / 3600;
      else ahNeg += (-avgI * dt) / 3600;

      const avgP = (p.signed_power + s.signed_power) / 2.0;
      if (avgP >= 0) whPos += (avgP * dt) / 3600;
      else whNeg += (-avgP * dt) / 3600;
    }
  }

  el.statMahForward.textContent = `${(ahPos * 1000).toFixed(2)} mAh`;
  el.statMahReverse.textContent = `${(ahNeg * 1000).toFixed(2)} mAh`;
  el.statMahNet.textContent = `${((ahPos - ahNeg) * 1000).toFixed(2)} mAh`;

  el.statMwhForward.textContent = `${(whPos * 1000).toFixed(2)} mWh`;
  el.statMwhReverse.textContent = `${(whNeg * 1000).toFixed(2)} mWh`;
  el.statMwhNet.textContent = `${((whPos - whNeg) * 1000).toFixed(2)} mWh`;

  const duration = state.samples[state.samples.length - 1].time - state.samples[0].time;
  el.statDuration.textContent = `${duration.toFixed(1)} с`;
}

// Load Saved Sessions
async function loadSessions() {
  try {
    const res = await fetch("/api/sessions");
    const data = await res.json();
    let html = "";

    if (!data.sessions || data.sessions.length === 0) {
      el.sessionsTableBody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">Немає збережених записів</td></tr>`;
      return;
    }

    for (const sess of data.sessions) {
      const sizeKb = (sess.size_bytes / 1024).toFixed(1);
      html += `
        <tr>
          <td><strong>${sess.id}</strong></td>
          <td>${new Date(sess.modified_at).toLocaleString("uk-UA")}</td>
          <td>${sess.sample_count}</td>
          <td>${sizeKb} KB</td>
          <td>
            <button class="btn btn-sm btn-primary" onclick="loadSessionToChart('${sess.id}')">📈 Відкрити</button>
            <button class="btn btn-sm btn-secondary" onclick="exportSession('${sess.id}', 'witrn_csv')">CSV (WITRN)</button>
            <button class="btn btn-sm btn-secondary" onclick="exportSession('${sess.id}', 'standard_csv')">CSV</button>
            <button class="btn btn-sm btn-secondary" onclick="exportSession('${sess.id}', 'json')">JSON</button>
            <button class="btn btn-sm btn-danger" onclick="deleteSession('${sess.id}')">🗑</button>
          </td>
        </tr>
      `;
    }
    el.sessionsTableBody.innerHTML = html;
  } catch (err) {
    console.error("Failed to load sessions", err);
  }
}

el.btnRefreshSessions.addEventListener("click", loadSessions);

window.loadSessionToChart = async function (sessionId) {
  try {
    const res = await fetch(`/api/sessions/${sessionId}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    state.samples = data.samples;
    state.timeWindow = 0; // Show all
    scheduleChartRender();
    alert(`Сесію "${sessionId}" (${data.samples.length} точок) завантажено на графік!`);
    // Switch to graph view
    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch (err) {
    alert(`Помилка завантаження сесії: ${err.message}`);
  }
};

window.exportSession = function (sessionId, format) {
  window.open(`/api/sessions/${sessionId}/export?format=${format}`, "_blank");
};

window.deleteSession = async function (sessionId) {
  if (!confirm(`Видалити сесію ${sessionId}?`)) return;
  await fetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
  loadSessions();
};

// Drag & Drop Import
el.dropZone.addEventListener("click", () => el.fileInput.click());
el.dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  el.dropZone.style.borderColor = "var(--border-focus)";
});
el.dropZone.addEventListener("dragleave", () => {
  el.dropZone.style.borderColor = "var(--border-color)";
});
el.dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  el.dropZone.style.borderColor = "var(--border-color)";
  if (e.dataTransfer.files.length > 0) {
    handleFileUpload(e.dataTransfer.files[0]);
  }
});
el.fileInput.addEventListener("change", (e) => {
  if (e.target.files.length > 0) {
    handleFileUpload(e.target.files[0]);
  }
});

async function handleFileUpload(file) {
  el.importStatus.innerHTML = `<p style="color:var(--border-focus)">Завантаження та обробка ${file.name}...</p>`;
  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/import", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    el.importStatus.innerHTML = `<p style="color:var(--btn-success)">✓ Успішно імпортовано ${data.sample_count} точок як сесію <strong>${data.session_id}</strong>!</p>`;
    loadSessions();
  } catch (err) {
    el.importStatus.innerHTML = `<p style="color:var(--btn-danger)">Помилка імпорту: ${err.message}</p>`;
  }
}

// Load Diagnostics Info
async function loadDiagnostics() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    el.systemDiagnostics.innerHTML = `
      <pre><code>${JSON.stringify(data, null, 2)}</code></pre>
    `;
  } catch (err) {
    el.systemDiagnostics.textContent = `Помилка отримання діагностики: ${err.message}`;
  }
}

// Start
resizeCanvas();
initWebSocket();
