const CONTROL_STREAM = "/control_stream";

// Persist form inputs so values remain after POST + redirect
const FORM_STORE_KEY = "sigma3_form_values_v2";

function saveFormValues() {
  try {
    const all = {};
    document.querySelectorAll("input[name], select[name], textarea[name]").forEach((el) => {
      all[el.name] = el.value;
    });
    localStorage.setItem(FORM_STORE_KEY, JSON.stringify(all));
  } catch (e) {}
}

function restoreFormValues() {
  try {
    const raw = localStorage.getItem(FORM_STORE_KEY);
    if (!raw) return;
    const all = JSON.parse(raw);
    document.querySelectorAll("input[name], select[name], textarea[name]").forEach((el) => {
      if (all[el.name] !== undefined) el.value = all[el.name];
    });
  } catch (e) {}
}

// ---------------- Stadium Preview (Sector + Seat Grid) ----------------
//
// Model:
// - 40 sections around an ellipse stadium (0..39). The Web UI uses section IDs like "A", "B", ... (base-26),
//   or numeric strings. We map to a section index [0..39].
// - Each section has a seat grid: ROWS x COLS = 20 x 50 (1000 seats).
// - "Seat LED" command lights a specific (row, col) inside a section.
// - Mexican wave animates across columns inside a section.
// - Sparkle randomly lights seats inside a section.
//

const SECTION_COUNT = 40;
const ROWS = 20;
const COLS = 50;

let lastCmd = null;
let lastCmdStartMs = 0;

function clamp01(x) {
  return Math.max(0, Math.min(1, x));
}

function rgbToCss(rgb, a = 1.0) {
  const r = Math.max(0, Math.min(255, rgb.r | 0));
  const g = Math.max(0, Math.min(255, rgb.g | 0));
  const b = Math.max(0, Math.min(255, rgb.b | 0));
  return `rgba(${r},${g},${b},${a})`;
}

function sectionIndexFromId(sectionId) {
  const s = String(sectionId || "").trim();
  if (!s) return 0;

  // numeric: "0".."39" or "1".."40"
  if (/^\d+$/.test(s)) {
    const n = parseInt(s, 10);
    if (n >= 0 && n < SECTION_COUNT) return n;
    if (n >= 1 && n <= SECTION_COUNT) return n - 1;
  }

  // alpha base-26: "A"=0, "B"=1, ..., "Z"=25, "AA"=26 ...
  let v = 0;
  const up = s.toUpperCase();
  for (let i = 0; i < up.length; i++) {
    const c = up.charCodeAt(i);
    if (c < 65 || c > 90) continue;
    v = v * 26 + (c - 65 + 1);
  }
  v = v - 1;
  if (isNaN(v) || v < 0) v = 0;
  return v % SECTION_COUNT;
}

function mulberry32(seed) {
  let t = seed >>> 0;
  return function () {
    t += 0x6d2b79f5;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

function buildSeatGridPositions(cx, cy, rxOut, ryOut, sectionIdx) {
  // Inner ring (pitch boundary) and outer ring (stands boundary)
  const rxIn = rxOut * 0.55;
  const ryIn = ryOut * 0.55;

  const wedge = (Math.PI * 2) / SECTION_COUNT;
  const start = -Math.PI / 2 + sectionIdx * wedge; // start at top
  const end = start + wedge;

  const pts = new Array(ROWS);
  for (let r = 0; r < ROWS; r++) {
    const fr = (r + 0.5) / ROWS;
    const rx = rxIn + fr * (rxOut - rxIn);
    const ry = ryIn + fr * (ryOut - ryIn);
    pts[r] = new Array(COLS);
    for (let c = 0; c < COLS; c++) {
      const fc = (c + 0.5) / COLS;
      const ang = start + fc * (end - start);
      pts[r][c] = {
        x: cx + rx * Math.cos(ang),
        y: cy + ry * Math.sin(ang),
      };
    }
  }
  return { pts, start, end, rxIn, ryIn };
}

function drawEllipse(ctx, cx, cy, rx, ry, stroke, lw = 2) {
  ctx.beginPath();
  ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
  ctx.strokeStyle = stroke;
  ctx.lineWidth = lw;
  ctx.stroke();
}

function drawWedgeOutlines(ctx, cx, cy, rxOut, ryOut) {
  const wedge = (Math.PI * 2) / SECTION_COUNT;
  ctx.strokeStyle = "rgb(220,223,230)";
  ctx.lineWidth = 1;

  for (let i = 0; i < SECTION_COUNT; i++) {
    const ang = -Math.PI / 2 + i * wedge;
    const x = cx + rxOut * Math.cos(ang);
    const y = cy + ryOut * Math.sin(ang);
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(x, y);
    ctx.stroke();
  }
}

function drawLedDot(ctx, x, y, rgb, intensity) {
  const core = 3.2;
  const glow = 7.5;
  const a = 0.10 + 0.90 * clamp01(intensity);

  // glow
  ctx.beginPath();
  ctx.arc(x, y, glow, 0, Math.PI * 2);
  ctx.fillStyle = rgbToCss(rgb, 0.12 * a);
  ctx.fill();

  // core
  ctx.beginPath();
  ctx.arc(x, y, core, 0, Math.PI * 2);
  ctx.fillStyle = rgbToCss(rgb, a);
  ctx.fill();
}

function computeSeatIntensity(cmd, nowMs, r0, c0) {
  // Default dim
  let intensity = 0.08;
  let rgb = { r: 80, g: 90, b: 110 };

  if (!cmd || cmd.type !== "led" || !cmd.payload) {
    return { rgb, intensity };
  }

  const p = cmd.payload;
  const pattern = p.pattern;

  if (pattern === "mexican_wave") {
    rgb = p.color || { r: 0, g: 120, b: 255 };
    const direction = p.direction || "left_to_right";
    const speed = Math.max(1, p.speed_seats_per_s || 12);
    const width = Math.max(1, p.width_seats || 3);
    const hold = Math.max(10, p.hold_ms || 120);

    // Move head across columns
    const t = (nowMs - lastCmdStartMs) / 1000.0; // seconds
    const headF = (t * speed) % COLS;
    let head = Math.floor(headF);

    if (direction === "right_to_left") head = (COLS - 1 - head + COLS) % COLS;

    const d = Math.abs(c0 - head);
    if (d <= width) {
      const fade = 1.0 - d / (width + 1);
      const pulse = 0.75 + 0.25 * Math.sin(((nowMs - lastCmdStartMs) % hold) / hold * Math.PI * 2);
      intensity = clamp01(fade * pulse);
    }
    return { rgb, intensity };
  }

  if (pattern === "sparkle") {
    const durationMs = Math.max(50, p.duration_ms || 8000);
    const density = Math.max(0.0, Math.min(1.0, p.density || 0.08));
    const seed = (p.seed || 42) + r0 * 997 + c0 * 101;
    rgb = p.color || { r: 0, g: 120, b: 255 };

    const elapsed = nowMs - lastCmdStartMs;
    if (elapsed > durationMs) return { rgb: { r: 80, g: 90, b: 110 }, intensity: 0.08 };

    // deterministic-ish sparkle per time bucket
    const bucket = Math.floor(nowMs / Math.max(40, p.spark_ms || 120));
    const rng = mulberry32(seed ^ bucket);
    if (rng() < density) {
      intensity = 0.65 + 0.35 * rng();
    }
    return { rgb, intensity };
  }

  if (pattern === "set_seat") {
    // Light specific row/col targets
    const targets = Array.isArray(p.targets) ? p.targets : [];
    for (const t of targets) {
      const rr = (t.row | 0);
      const cc = (t.col | 0);
      if (rr === (r0 + 1) && cc === (c0 + 1)) {
        rgb = t.rgb || { r: 255, g: 0, b: 0 };
        const dur = Math.max(0, t.duration_ms || 800);
        const elapsed = nowMs - lastCmdStartMs;
        if (dur === 0 || elapsed <= dur) {
          // gentle blink
          const blink = 0.65 + 0.35 * Math.sin(elapsed / 120 * Math.PI * 2);
          intensity = clamp01(blink);
          return { rgb, intensity };
        }
      }
    }
    return { rgb: { r: 80, g: 90, b: 110 }, intensity: 0.08 };
  }

  return { rgb, intensity };
}

function startPreview() {
  const canvas = document.getElementById("stadiumCanvas");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  const W = canvas.width;
  const H = canvas.height;
  const cx = W * 0.5;
  const cy = H * 0.52;

  const rxOut = W * 0.42;
  const ryOut = H * 0.32;

  function frame() {
    const nowMs = performance.now();

    // Background
    ctx.clearRect(0, 0, W, H);
    drawEllipse(ctx, cx, cy, rxOut * 0.55, ryOut * 0.55, "rgb(240,243,248)", 0); // filled pitch
    drawEllipse(ctx, cx, cy, rxOut * 0.55, ryOut * 0.55, "rgb(230,233,240)", 2);
    drawEllipse(ctx, cx, cy, rxOut, ryOut, "rgb(200,205,215)", 2);
    drawWedgeOutlines(ctx, cx, cy, rxOut, ryOut);

    // Decide which section to render seats for
    const sectionId = (lastCmd && (lastCmd.section_id || (lastCmd.payload && lastCmd.payload.section_id))) || "A";
    const sectionIdx = sectionIndexFromId(sectionId);

    // Draw seats for active section
    const grid = buildSeatGridPositions(cx, cy, rxOut, ryOut, sectionIdx);
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        const p = grid.pts[r][c];
        const si = computeSeatIntensity(lastCmd, nowMs, r, c);
        drawLedDot(ctx, p.x, p.y, si.rgb, si.intensity);
      }
    }

    // Label
    ctx.fillStyle = "rgb(90,95,105)";
    ctx.font = "14px system-ui, -apple-system, Segoe UI, Roboto, sans-serif";
    ctx.fillText(`Section ${sectionId} (preview) — ${ROWS}x${COLS} seats`, 16, 24);

    requestAnimationFrame(frame);
  }

  requestAnimationFrame(frame);
}

// Listen to server control stream so preview updates immediately when buttons are clicked
function startControlStream() {
  try {
    const es = new EventSource(CONTROL_STREAM);
    es.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg && msg.type === "preview" && msg.command) {
          lastCmd = msg.command;
          lastCmdStartMs = performance.now();
        }
      } catch (e) {}
    };
  } catch (e) {}
}

document.addEventListener("DOMContentLoaded", () => {
  restoreFormValues();
  document.querySelectorAll("form").forEach((f) => {
    f.addEventListener("submit", () => saveFormValues());
  });

  startControlStream();
  startPreview();
});
