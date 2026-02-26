// Sigma3 Stadium Preview Renderer (client-side)
// - Draws an ellipse stadium + section wedges
// - Simulates LED patterns (mexican_wave, sparkle, set_pixel) as flashing dots
//
// The browser polls /api/preview/poll for the latest preview event.
// This preview is independent of real hardware.

const canvas = document.getElementById("stadiumCanvas");

if (!canvas) {
  console.log("Preview canvas not found.");
} else {
  const ctx = canvas.getContext("2d");

  const W = canvas.width;
  const H = canvas.height;

  const cx = W / 2;
  const cy = H / 2;

  const rx = W * 0.42;
  const ry = H * 0.30;

  // Demo sections rendered in preview (1-10)
  // NOTE: If server sends "ALL", we expand to these keys.
  const sectionKeys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"];

  // Build wedge definitions
  const sections = {};
  for (let i = 0; i < sectionKeys.length; i++) {
    const key = sectionKeys[i];
    const start = -Math.PI + (i * (2 * Math.PI / sectionKeys.length));
    const end = -Math.PI + ((i + 1) * (2 * Math.PI / sectionKeys.length));
    sections[key] = { start, end };
  }

  // Current animation state
  let active = {
    pattern: null,
    sections: [],
    params: {},
    startTs: performance.now(),
  };

  // ---------- helpers ----------
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  function rgbCss(rgb, alpha = 1.0) {
    const r = clamp((rgb && rgb.r != null) ? rgb.r : 0, 0, 255);
    const g = clamp((rgb && rgb.g != null) ? rgb.g : 180, 0, 255);
    const b = clamp((rgb && rgb.b != null) ? rgb.b : 255, 0, 255);
    return `rgba(${r},${g},${b},${alpha})`;
  }

  function clear() {
    ctx.clearRect(0, 0, W, H);
  }

  function pointOnEllipse(theta, inset = 1.0) {
    return {
      x: cx + (rx * inset) * Math.cos(theta),
      y: cy + (ry * inset) * Math.sin(theta),
    };
  }

  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  function drawStadiumBase() {
    // Outer ellipse
    ctx.beginPath();
    ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
    ctx.strokeStyle = "#666";
    ctx.lineWidth = 2;
    ctx.stroke();

    // Wedge boundaries
    ctx.strokeStyle = "#333";
    ctx.lineWidth = 2;

    for (const key of Object.keys(sections)) {
      const s = sections[key];
      const p1 = pointOnEllipse(s.start, 1.0);
      const p2 = pointOnEllipse(s.end, 1.0);

      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(p1.x, p1.y);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(p2.x, p2.y);
      ctx.stroke();
    }
  }

  // Sample N "seat LEDs" along a curve near the outer boundary of a wedge
  function sampleSeatDots(sectionId, seatCount = 80, inset = 0.92) {
    const s = sections[sectionId];
    if (!s) return [];
    const dots = [];
    for (let i = 0; i < seatCount; i++) {
      const t = seatCount === 1 ? 0.5 : i / (seatCount - 1);
      const theta = lerp(s.start, s.end, t);
      const p = pointOnEllipse(theta, inset);
      dots.push({ i, t, theta, x: p.x, y: p.y });
    }
    return dots;
  }

  function expandSections(inputSections) {
    // If server sends null/empty, or includes "ALL", expand to preview keys.
    if (!Array.isArray(inputSections) || inputSections.length === 0) return [...sectionKeys];

    const upper = inputSections.map(s => String(s).trim().toUpperCase()).filter(Boolean);
    if (upper.includes("ALL")) return [...sectionKeys];

    // keep only known preview wedges
    return upper.filter(s => sections[s]);
  }

  // ---------- render patterns ----------
  function renderPattern(nowTs) {
    const elapsed = nowTs - active.startTs;

    clear();
    drawStadiumBase();

    if (!active.pattern) return;

    const rgb = active.params.rgb || active.params.rgb_value || { r: 0, g: 180, b: 255 };
    const targetSections = expandSections(active.sections);

    for (const sid of targetSections) {
      if (!sections[sid]) continue;

      if (active.pattern === "mexican_wave") {
        const seatCount = 90;
        const dots = sampleSeatDots(sid, seatCount, 0.93);

        const speed = Number(active.params.speed_seats_per_s ?? 12);
        const width = Number(active.params.width_seats ?? 3);
        const holdMs = Number(active.params.hold_ms ?? 120);
        const dir = String(active.params.direction ?? "left_to_right");

        const seatsPerMs = speed / 1000.0;
        const head = (elapsed * seatsPerMs) % seatCount;

        const idxMap = (i) => (dir === "right_to_left" ? (seatCount - 1 - i) : i);

        for (let i = 0; i < seatCount; i++) {
          const mapped = idxMap(i);
          const dist = Math.abs(mapped - head);

          // A "bright band" around the head + a soft tail
          const isCore = dist <= width;
          const isTail = dist <= (width * 3);

          // Blink makes it look like LEDs “spark” rather than a flat fill
          const blink = 0.55 + 0.45 * Math.abs(Math.sin((elapsed / Math.max(holdMs, 40)) + i * 0.22));

          let alpha = 0.06;    // background faint
          let radius = 2.8;

          if (isTail) {
            alpha = 0.18;
            radius = 3.4;
          }
          if (isCore) {
            alpha = 0.95 * blink;
            radius = 6.5;
          }

          ctx.beginPath();
          ctx.arc(dots[i].x, dots[i].y, radius, 0, Math.PI * 2);
          ctx.fillStyle = rgbCss(rgb, alpha);
          ctx.fill();
        }

      } else if (active.pattern === "sparkle") {
        const seatCount = 110;
        const dots = sampleSeatDots(sid, seatCount, 0.93);

        const duration = Number(active.params.duration_ms ?? 8000);
        const density = Number(active.params.density ?? 0.08);
        const seed = Number(active.params.seed ?? 42);

        // deterministic pseudo-random
        function rand01(i, t) {
          const x = Math.sin((i * 999 + t * 0.002 + seed) * 12.9898) * 43758.5453;
          return x - Math.floor(x);
        }

        for (let i = 0; i < dots.length; i++) {
          const r01 = rand01(i, elapsed);
          const isOn = r01 < density;

          // stronger flicker for ON dots
          const blink = 0.35 + 0.65 * Math.abs(Math.sin(elapsed / 120 + i * 0.6));

          const alpha = isOn ? (0.95 * blink) : 0.05;
          const radius = isOn ? 5.8 : 2.6;

          ctx.beginPath();
          ctx.arc(dots[i].x, dots[i].y, radius, 0, Math.PI * 2);
          ctx.fillStyle = rgbCss(rgb, alpha);
          ctx.fill();
        }

        if (elapsed > duration) {
          active.pattern = null;
        }

      } else if (active.pattern === "set_pixel") {
        const seatCount = 90;
        const dots = sampleSeatDots(sid, seatCount, 0.93);

        const row = Number(active.params.row ?? 1);
        const col = Number(active.params.col ?? 1);
        const holdMs = Number(active.params.hold_ms ?? 500);

        // Demo mapping: map (row,col) -> seat index.
        // You can replace this later with your real seat mapping logic.
        const idx = clamp(((row - 1) * 10 + (col - 1)) % seatCount, 0, seatCount - 1);

        // faint background
        for (let i = 0; i < dots.length; i++) {
          ctx.beginPath();
          ctx.arc(dots[i].x, dots[i].y, 2.3, 0, Math.PI * 2);
          ctx.fillStyle = "rgba(80,80,90,0.10)";
          ctx.fill();
        }

        // blink target pixel
        const blink = 0.25 + 0.75 * Math.abs(Math.sin(elapsed / 120));
        ctx.beginPath();
        ctx.arc(dots[idx].x, dots[idx].y, 7.5, 0, Math.PI * 2);
        ctx.fillStyle = rgbCss(rgb, 0.98 * blink);
        ctx.fill();

        if (elapsed > holdMs) {
          active.pattern = null;
        }
      }
    }
  }

  function tick(nowTs) {
    try {
      renderPattern(nowTs);
    } catch (e) {
      // If rendering fails for any reason, do not kill the UI loop.
      console.warn("Preview render error:", e);
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);

  // ---------- poll preview events from server ----------
  async function poll() {
    try {
      const res = await fetch("/api/preview/poll", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const evt = await res.json();

      // Expected: { kind:"led", pattern:"mexican_wave|sparkle|set_pixel", sections:[...], params:{...} }
      if (evt && evt.kind === "led" && evt.pattern) {
        active.pattern = String(evt.pattern);
        active.sections = Array.isArray(evt.sections) ? evt.sections : [];
        active.params = (evt.params && typeof evt.params === "object") ? evt.params : {};
        active.startTs = performance.now();
      }
    } catch (e) {
      // ignore transient errors
    }
    setTimeout(poll, 200); // 5Hz
  }
  poll();
}
