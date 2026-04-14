const historyBody = document.getElementById("owner-history-body");
const failuresBody = document.getElementById("owner-failures-body");
const statusBox = document.getElementById("status");
const monitoringMeta = document.getElementById("monitoring-meta");
const clearFailuresBtn = document.getElementById("clear-failures");

const metricTotal = document.getElementById("metric-total");
const metricUsers = document.getElementById("metric-users");
const metricPages = document.getElementById("metric-pages");
const metricFailures = document.getElementById("metric-failures");

function setStatus(message, isError = false) {
  statusBox.textContent = message;
  statusBox.classList.toggle("error", isError);
}

function formatDateTime(isoDate) {
  const date = new Date(isoDate);
  if (Number.isNaN(date.getTime())) return "Unknown time";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function shortLink(url) {
  try {
    const u = new URL(url);
    const previewPath = u.pathname.length > 18 ? `${u.pathname.slice(0, 18)}...` : u.pathname;
    return `${u.hostname}${previewPath || "/"}`;
  } catch {
    return url || "-";
  }
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function setEmpty(bodyNode, colspan, text) {
  bodyNode.innerHTML = "";
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = colspan;
  cell.className = "history-empty";
  cell.textContent = text;
  row.appendChild(cell);
  bodyNode.appendChild(row);
}

function renderHistory(items) {
  metricTotal.textContent = String(items.length);
  metricUsers.textContent = String(new Set(items.map((x) => x.client_ip || "unknown")).size);
  metricPages.textContent = String(new Set(items.map((x) => x.source_page || "unknown")).size);

  if (!items.length) {
    setEmpty(historyBody, 7, "No downloads yet.");
    return;
  }

  historyBody.innerHTML = "";
  for (const item of items) {
    const row = document.createElement("tr");
    const safeUrl = item.source_url || "#";
    row.innerHTML = `
      <td>${esc(item.title || "Untitled media")}</td>
      <td><span class="type-pill ${item.kind === "audio" ? "audio" : "video"}">${item.kind === "audio" ? "Audio" : "Video"}</span></td>
      <td>${esc(item.source_page || "-")}</td>
      <td>${esc(item.client_ip || "-")}</td>
      <td class="owner-agent">${esc(item.user_agent || "-")}</td>
      <td>${esc(formatDateTime(item.created_at))}</td>
      <td><a class="history-link" href="${esc(safeUrl)}" target="_blank" rel="noopener noreferrer">${esc(shortLink(item.source_url))}</a></td>
    `;
    historyBody.appendChild(row);
  }
}

function renderFailures(items) {
  metricFailures.textContent = String(items.length);

  if (!items.length) {
    setEmpty(failuresBody, 6, "No failures yet.");
    return;
  }

  failuresBody.innerHTML = "";
  for (const item of items) {
    const row = document.createElement("tr");
    const safeUrl = item.source_url || "#";
    row.innerHTML = `
      <td>${esc(item.stage || "-")}</td>
      <td class="owner-agent">${esc(item.error || "-")}</td>
      <td>${esc(item.source_page || "-")}</td>
      <td>${esc(item.client_ip || "-")}</td>
      <td>${esc(formatDateTime(item.created_at))}</td>
      <td><a class="history-link" href="${esc(safeUrl)}" target="_blank" rel="noopener noreferrer">${esc(shortLink(item.source_url))}</a></td>
    `;
    failuresBody.appendChild(row);
  }
}

function renderMonitoring(monitoring) {
  if (!monitoring) return;
  const uptime = Number(monitoring.uptime_seconds || 0);
  const h = Math.floor(uptime / 3600);
  const m = Math.floor((uptime % 3600) / 60);
  monitoringMeta.textContent = `Uptime: ${h}h ${m}m | Sentry: ${monitoring.sentry_enabled ? "enabled" : "disabled"}`;
}

async function load() {
  try {
    const [historyRes, failuresRes, monitoringRes] = await Promise.all([
      fetch("/api/history", { cache: "no-store" }),
      fetch("/api/failures", { cache: "no-store" }),
      fetch("/api/monitoring", { cache: "no-store" }),
    ]);

    const historyPayload = await historyRes.json();
    const failuresPayload = await failuresRes.json();
    const monitoringPayload = await monitoringRes.json();

    if (!historyRes.ok) throw new Error(historyPayload.detail || "Failed to load history.");
    if (!failuresRes.ok) throw new Error(failuresPayload.detail || "Failed to load failures.");
    if (!monitoringRes.ok) throw new Error(monitoringPayload.detail || "Failed to load monitoring.");

    renderHistory(Array.isArray(historyPayload.items) ? historyPayload.items : []);
    renderFailures(Array.isArray(failuresPayload.items) ? failuresPayload.items : []);
    renderMonitoring(monitoringPayload);

    if (statusBox.classList.contains("error")) setStatus("");
  } catch (err) {
    setStatus(err.message || "Could not load owner dashboard data.", true);
    setEmpty(historyBody, 7, "No downloads yet.");
    setEmpty(failuresBody, 6, "No failures yet.");
  }
}

clearFailuresBtn.addEventListener("click", async () => {
  try {
    const response = await fetch("/api/failures", { method: "DELETE" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Failed to clear failures.");
    setStatus("Failure log cleared.");
    renderFailures([]);
  } catch (err) {
    setStatus(err.message || "Could not clear failure log.", true);
  }
});

load();
setInterval(load, 5000);
