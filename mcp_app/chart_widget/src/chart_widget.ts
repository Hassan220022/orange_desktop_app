const root = document.getElementById("chart-root");
const SUPPORTED = new Set(["bar", "horizontal_bar", "line", "donut", "pie", "heatmap", "histogram", "scatter"]);

function css() {
  return `
    <style>
      :root { color-scheme: light dark; }
      body { margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
      .wrap { padding: 14px; color: #111827; background: #ffffff; }
      @media (prefers-color-scheme: dark) { .wrap { color: #f3f4f6; background: #111827; } .muted { color: #9ca3af; } }
      .title { font-size: 18px; font-weight: 700; margin-bottom: 6px; }
      .muted { color: #6b7280; font-size: 12px; }
      .meta { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0 12px; }
      .pill { border: 1px solid #d1d5db; border-radius: 999px; padding: 3px 8px; font-size: 12px; }
      .warning { background: #fef3c7; color: #92400e; border-radius: 8px; padding: 8px; margin: 8px 0; }
      .empty { border: 1px dashed #d1d5db; border-radius: 12px; padding: 20px; text-align: center; }
      .bars { display: grid; gap: 8px; }
      .bar-row { display: grid; grid-template-columns: minmax(90px, 30%) 1fr 56px; gap: 8px; align-items: center; font-size: 12px; }
      .bar-track { height: 12px; border-radius: 999px; background: #e5e7eb; overflow: hidden; }
      .bar-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #2563eb, #22c55e); }
      svg { width: 100%; height: 260px; overflow: visible; }
      .fallback { border: 1px solid #d1d5db; border-radius: 12px; padding: 12px; }
      table { width: 100%; border-collapse: collapse; font-size: 12px; } th, td { text-align: left; border-bottom: 1px solid #e5e7eb; padding: 6px; }
    </style>
  `;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char] || char));
}

function numberValue(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function points(payload) {
  if (payload && Array.isArray(payload.series) && payload.series.length) return payload.series;
  const labels = payload && Array.isArray(payload.labels) ? payload.labels : [];
  const values = payload && Array.isArray(payload.values) ? payload.values : [];
  return labels.map((label, index) => ({ label, value: numberValue(values[index]) }));
}

function maxValue(items) {
  return Math.max(1, ...items.map((item) => numberValue(item.value ?? item.y)));
}

function renderBars(items) {
  const max = maxValue(items);
  return `<div class="bars">${items.map((item) => {
    const value = numberValue(item.value);
    const pct = Math.max(0, Math.min(100, (value / max) * 100));
    return `<div class="bar-row"><div>${escapeHtml(item.label)}</div><div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div><div>${escapeHtml(value)}</div></div>`;
  }).join("")}</div>`;
}

function renderLine(items) {
  const max = maxValue(items);
  const width = 640;
  const height = 220;
  const step = items.length > 1 ? width / (items.length - 1) : width;
  const coords = items.map((item, index) => {
    const yValue = numberValue(item.value ?? item.y);
    const x = items.length > 1 ? index * step : width / 2;
    const y = height - (yValue / max) * (height - 20) + 10;
    return `${x},${y}`;
  }).join(" ");
  return `<svg viewBox="0 0 ${width} ${height}"><polyline points="${coords}" fill="none" stroke="#2563eb" stroke-width="3"/>${coords.split(" ").filter(Boolean).map((pair) => {
    const [x, y] = pair.split(",");
    return `<circle cx="${x}" cy="${y}" r="4" fill="#22c55e"/>`;
  }).join("")}</svg>`;
}

function renderScatter(items) {
  const width = 640;
  const height = 220;
  const xs = items.map((item) => numberValue(item.x));
  const ys = items.map((item) => numberValue(item.y ?? item.value));
  const maxX = Math.max(1, ...xs);
  const maxY = Math.max(1, ...ys);
  return `<svg viewBox="0 0 ${width} ${height}">${items.map((item) => {
    const x = (numberValue(item.x) / maxX) * (width - 30) + 15;
    const y = height - (numberValue(item.y ?? item.value) / maxY) * (height - 30) - 15;
    return `<circle cx="${x}" cy="${y}" r="5" fill="#2563eb"><title>${escapeHtml(item.label)}</title></circle>`;
  }).join("")}</svg>`;
}

function renderDonut(items) {
  const total = items.reduce((sum, item) => sum + Math.max(0, numberValue(item.value)), 0) || 1;
  let offset = 0;
  const colors = ["#2563eb", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];
  const rings = items.map((item, index) => {
    const value = Math.max(0, numberValue(item.value));
    const dash = (value / total) * 100;
    const circle = `<circle r="70" cx="110" cy="110" fill="transparent" stroke="${colors[index % colors.length]}" stroke-width="34" stroke-dasharray="${dash} ${100 - dash}" stroke-dashoffset="${-offset}"/>`;
    offset += dash;
    return circle;
  }).join("");
  return `<svg viewBox="0 0 420 220"><g transform="rotate(-90 110 110)">${rings}</g><circle cx="110" cy="110" r="48" fill="white" opacity="0.9"/><foreignObject x="220" y="20" width="190" height="180"><div xmlns="http://www.w3.org/1999/xhtml">${renderLegend(items)}</div></foreignObject></svg>`;
}

function renderLegend(items) {
  return items.map((item) => `<div class="muted">${escapeHtml(item.label)}: ${escapeHtml(item.value)}</div>`).join("");
}

function renderTable(items) {
  return `<div class="fallback"><div class="muted">Fallback table for advanced chart kind.</div><table><thead><tr><th>Label</th><th>Value</th></tr></thead><tbody>${items.map((item) => `<tr><td>${escapeHtml(item.label ?? item.x)}</td><td>${escapeHtml(item.value ?? item.y)}</td></tr>`).join("")}</tbody></table></div>`;
}

function renderChart(payload) {
  const kind = String(payload.chart_kind || "bar");
  const items = points(payload);
  if (payload.empty_state || items.length === 0) {
    return `<div class="empty"><strong>${escapeHtml(payload.empty_state?.title || "No chart data")}</strong><div class="muted">${escapeHtml(payload.empty_state?.message || "No rows matched the selected chart and filters.")}</div></div>`;
  }
  if (!SUPPORTED.has(kind)) return renderTable(items);
  if (kind === "line") return renderLine(items);
  if (kind === "scatter") return renderScatter(items);
  if (kind === "donut" || kind === "pie") return renderDonut(items);
  return renderBars(items);
}

function render(payload) {
  if (!root) return;
  const fallback = window.openai?.toolOutput || window.openai?.toolInput || {};
  const data = payload && typeof payload === "object" ? payload : fallback;
  const quality = data.data_quality || {};
  const filters = data.query_context?.filters || {};
  const itemCount = points(data).length;
  const warningHtml = Array.isArray(data.warnings) && data.warnings.length
    ? data.warnings.map((warning) => `<div class="warning">${escapeHtml(warning)}</div>`).join("")
    : "";
  root.innerHTML = `${css()}<div class="wrap">
    <div class="title">${escapeHtml(data.title || data.chart_id || "Chart")}</div>
    <div class="meta">
      <span class="pill">${escapeHtml(data.chart_kind || "chart")}</span>
      <span class="pill">${escapeHtml(quality.returned_points ?? itemCount)} shown / ${escapeHtml(quality.total_points ?? itemCount)} points</span>
      ${Object.keys(filters).length ? `<span class="pill">Filters: ${escapeHtml(JSON.stringify(filters))}</span>` : ""}
    </div>
    ${warningHtml}
    ${renderChart(data)}
  </div>`;
}

render();

window.addEventListener("message", (event) => {
  if (event.source !== window.parent) return;
  const message = event.data;
  if (!message || message.jsonrpc !== "2.0") return;
  if (message.method !== "ui/notifications/tool-result") return;
  render(message.params?.structuredContent);
}, { passive: true });

window.addEventListener("openai:set_globals", (event) => {
  render(event.detail?.globals?.toolOutput || window.openai?.toolOutput);
}, { passive: true });
