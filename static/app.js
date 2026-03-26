const form = document.getElementById("analyze-form");
const urlInput = document.getElementById("url-input");
const analyzeBtn = document.getElementById("analyze-btn");
const statusBox = document.getElementById("status");
const resultSection = document.getElementById("result");
const titleNode = document.getElementById("title");
const uploaderNode = document.getElementById("uploader");
const durationNode = document.getElementById("duration");
const thumbNode = document.getElementById("thumb");

const videoFormatSelect = document.getElementById("video-format");
const audioFormatIdSelect = document.getElementById("audio-format-id");
const audioFileFormatSelect = document.getElementById("audio-file-format");
const downloadVideoBtn = document.getElementById("download-video");
const downloadAudioBtn = document.getElementById("download-audio");

let currentInfo = null;

function setStatus(message, isError = false) {
  statusBox.textContent = message;
  statusBox.classList.toggle("error", isError);
}

function formatDuration(seconds) {
  if (!seconds || Number.isNaN(seconds)) return "Duration: unknown";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `Duration: ${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `Duration: ${m}:${String(s).padStart(2, "0")}`;
}

function fillSelect(select, options) {
  select.innerHTML = "";
  for (const option of options) {
    const el = document.createElement("option");
    el.value = option.format_id;
    el.textContent = option.label;
    select.appendChild(el);
  }
}

function setLoading(loading) {
  analyzeBtn.disabled = loading;
  analyzeBtn.textContent = loading ? "Analyzing..." : "Analyze";
}

async function analyzeUrl(url) {
  setLoading(true);
  setStatus("Reading video details...");
  resultSection.classList.add("hidden");
  currentInfo = null;

  try {
    const response = await fetch("/api/info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Failed to analyze URL.");

    currentInfo = payload;
    titleNode.textContent = payload.title || "Untitled media";
    uploaderNode.textContent = `Uploader: ${payload.uploader || "Unknown"}`;
    durationNode.textContent = formatDuration(Number(payload.duration));
    thumbNode.src = payload.thumbnail || "";
    thumbNode.style.display = payload.thumbnail ? "block" : "none";

    fillSelect(videoFormatSelect, payload.video_options || []);
    fillSelect(audioFormatIdSelect, payload.audio_options || []);

    resultSection.classList.remove("hidden");
    setStatus("Ready. Choose your options and download.");
  } catch (err) {
    setStatus(err.message || "Something went wrong.", true);
  } finally {
    setLoading(false);
  }
}

function buildDownloadUrl(kind) {
  if (!currentInfo) return null;

  const params = new URLSearchParams();
  params.set("url", currentInfo.source_url);
  params.set("kind", kind);

  if (kind === "video") {
    params.set("format_id", videoFormatSelect.value || "best");
  } else {
    params.set("format_id", audioFormatIdSelect.value || "bestaudio");
    params.set("audio_format", audioFileFormatSelect.value || "mp3");
  }
  return `/api/download?${params.toString()}`;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const url = urlInput.value.trim();
  if (!url) {
    setStatus("Please enter a video URL first.", true);
    return;
  }
  await analyzeUrl(url);
});

downloadVideoBtn.addEventListener("click", () => {
  const target = buildDownloadUrl("video");
  if (!target) {
    setStatus("Analyze a URL first.", true);
    return;
  }
  window.open(target, "_blank", "noopener,noreferrer");
});

downloadAudioBtn.addEventListener("click", () => {
  const target = buildDownloadUrl("audio");
  if (!target) {
    setStatus("Analyze a URL first.", true);
    return;
  }
  window.open(target, "_blank", "noopener,noreferrer");
});
