const bodyNode = document.getElementById("owner-history-body");
const statusBox = document.getElementById("status");
const metricTotal = document.getElementById("metric-total");
const metricUsers = document.getElementById("metric-users");
const metricPages = document.getElementById("metric-pages");

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

function setEmptyState() {
  bodyNode.innerHTML = "";
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = 7;
  cell.className = "history-empty";
  cell.textContent = "No downloads yet.";
  row.appendChild(cell);
  bodyNode.appendChild(row);
}

function render(items) {
  metricTotal.textContent = String(items.length);
  metricUsers.textContent = String(new Set(items.map((x) => x.client_ip || "unknown")).size);
  metricPages.textContent = String(new Set(items.map((x) => x.source_page || "unknown")).size);

  if (!items.length) {
    setEmptyState();
    return;
  }

  bodyNode.innerHTML = "";
  for (const item of items) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${item.title || "Untitled media"}</td>
      <td><span class="type-pill ${item.kind === "audio" ? "audio" : "video"}">${item.kind === "audio" ? "Audio" : "Video"}</span></td>
      <td>${item.source_page || "-"}</td>
      <td>${item.client_ip || "-"}</td>
      <td class="owner-agent">${item.user_agent || "-"}</td>
      <td>${formatDateTime(item.created_at)}</td>
      <td><a class="history-link" href="${item.source_url || "#"}" target="_blank" rel="noopener noreferrer">${shortLink(item.source_url)}</a></td>
    `;
    bodyNode.appendChild(row);
  }
}

async function load() {
  try {
    const res = await fetch("/api/history", { cache: "no-store" });
    const payload = await res.json();
    if (!res.ok) throw new Error(payload.detail || "Failed to load history.");
    render(Array.isArray(payload.items) ? payload.items : []);
    if (statusBox.classList.contains("error")) setStatus("");
  } catch (err) {
    setStatus(err.message || "Could not load history.", true);
    setEmptyState();
  }
}

load();
setInterval(load, 5000);
