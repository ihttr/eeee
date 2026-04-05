const historyBody = document.getElementById("history-body");
const clearHistoryBtn = document.getElementById("clear-history");
const metricTotal = document.getElementById("metric-total");
const metricVideo = document.getElementById("metric-video");
const metricAudio = document.getElementById("metric-audio");
const statusBox = document.getElementById("status");

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
    const previewPath = u.pathname.length > 20 ? `${u.pathname.slice(0, 20)}...` : u.pathname;
    return `${u.hostname}${previewPath || "/"}`;
  } catch {
    return url;
  }
}

function setEmptyState() {
  historyBody.innerHTML = "";
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = 6;
  cell.className = "history-empty";
  cell.textContent = "No downloads yet.";
  row.appendChild(cell);
  historyBody.appendChild(row);
}

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    setStatus("Link copied.");
  } catch {
    setStatus("Clipboard not allowed in this browser.", true);
  }
}

function renderHistory(items) {
  const videoCount = items.filter((item) => item.kind === "video").length;
  const audioCount = items.filter((item) => item.kind === "audio").length;

  metricTotal.textContent = String(items.length);
  metricVideo.textContent = String(videoCount);
  metricAudio.textContent = String(audioCount);

  if (!items.length) {
    setEmptyState();
    return;
  }

  historyBody.innerHTML = "";
  for (const item of items) {
    const row = document.createElement("tr");

    const titleCell = document.createElement("td");
    titleCell.textContent = item.title || "Untitled media";
    row.appendChild(titleCell);

    const typeCell = document.createElement("td");
    const typePill = document.createElement("span");
    typePill.className = `type-pill ${item.kind === "audio" ? "audio" : "video"}`;
    typePill.textContent = item.kind === "audio" ? "Audio" : "Video";
    typeCell.appendChild(typePill);
    row.appendChild(typeCell);

    const formatCell = document.createElement("td");
    formatCell.textContent = item.format || "Auto";
    row.appendChild(formatCell);

    const timeCell = document.createElement("td");
    timeCell.textContent = formatDateTime(item.created_at);
    row.appendChild(timeCell);

    const linkCell = document.createElement("td");
    const link = document.createElement("a");
    link.href = item.source_url || "#";
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.className = "history-link";
    link.textContent = shortLink(item.source_url || "");
    linkCell.appendChild(link);
    row.appendChild(linkCell);

    const actionsCell = document.createElement("td");
    const actions = document.createElement("div");
    actions.className = "row-actions";

    const reDownload = document.createElement("button");
    reDownload.type = "button";
    reDownload.textContent = "Re-download";
    reDownload.addEventListener("click", () => {
      if (!item.download_url) {
        setStatus("Missing download URL for this entry.", true);
        return;
      }
      window.open(item.download_url, "_blank", "noopener,noreferrer");
    });

    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.textContent = "Copy Link";
    copyBtn.addEventListener("click", () => copyToClipboard(item.source_url || ""));

    actions.appendChild(reDownload);
    actions.appendChild(copyBtn);
    actionsCell.appendChild(actions);
    row.appendChild(actionsCell);
    historyBody.appendChild(row);
  }
}

async function loadHistory() {
  try {
    const response = await fetch("/api/history", { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Failed to load history.");
    }
    renderHistory(Array.isArray(payload.items) ? payload.items : []);
    if (statusBox.classList.contains("error")) {
      setStatus("");
    }
  } catch (err) {
    setStatus(err.message || "Could not load history.", true);
    setEmptyState();
  }
}

clearHistoryBtn.addEventListener("click", async () => {
  try {
    const response = await fetch("/api/history", { method: "DELETE" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Failed to clear history.");
    }
    setStatus("History cleared.");
    renderHistory([]);
  } catch (err) {
    setStatus(err.message || "Could not clear history.", true);
  }
});

loadHistory();
setInterval(loadHistory, 5000);
