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

const pageMode = (document.body.dataset.pageMode || "all").toLowerCase();
const defaultAudioFormat = (document.body.dataset.defaultAudioFormat || "mp3").toLowerCase();

let currentInfo = null;

function setStatus(message, isError = false) {
  if (!statusBox) return;
  statusBox.textContent = message;
  statusBox.classList.toggle("error", isError);
}

function selectedOptionLabel(select) {
  if (!select || !select.options.length) return "Auto";
  return select.options[select.selectedIndex]?.text || "Auto";
}

function hasOption(select, value) {
  if (!select) return false;
  return [...select.options].some((option) => option.value === value);
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
  if (!select) return;
  select.innerHTML = "";
  for (const option of options) {
    const el = document.createElement("option");
    el.value = option.format_id;
    el.textContent = option.label;
    select.appendChild(el);
  }
}

function setLoading(loading) {
  if (!analyzeBtn) return;
  analyzeBtn.disabled = loading;
  analyzeBtn.textContent = loading ? "Analyzing..." : "Analyze";
}

function applyDefaultsAfterAnalyze() {
  if (audioFileFormatSelect && hasOption(audioFileFormatSelect, defaultAudioFormat)) {
    audioFileFormatSelect.value = defaultAudioFormat;
  }
}

async function analyzeUrl(url) {
  setLoading(true);
  setStatus("Reading video details...");
  if (resultSection) resultSection.classList.add("hidden");
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
    if (titleNode) titleNode.textContent = payload.title || "Untitled media";
    if (uploaderNode) uploaderNode.textContent = `Uploader: ${payload.uploader || "Unknown"}`;
    if (durationNode) durationNode.textContent = formatDuration(Number(payload.duration));
    if (thumbNode) {
      thumbNode.src = payload.thumbnail || "";
      thumbNode.style.display = payload.thumbnail ? "block" : "none";
    }

    fillSelect(videoFormatSelect, payload.video_options || []);
    fillSelect(audioFormatIdSelect, payload.audio_options || []);
    applyDefaultsAfterAnalyze();

    if (resultSection) resultSection.classList.remove("hidden");
    if (pageMode === "audio") {
      setStatus("Ready. Choose audio stream and download.");
    } else {
      setStatus("Ready. Choose your options and download.");
    }
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
    if (!videoFormatSelect) return null;
    params.set("format_id", videoFormatSelect.value || "best");
    params.set("format_label", selectedOptionLabel(videoFormatSelect));
  } else {
    if (!audioFormatIdSelect) return null;
    params.set("format_id", audioFormatIdSelect.value || "bestaudio");
    const finalAudioFormat = audioFileFormatSelect?.value || defaultAudioFormat || "mp3";
    params.set("audio_format", finalAudioFormat);
    params.set("format_label", `${selectedOptionLabel(audioFormatIdSelect)} -> ${finalAudioFormat.toUpperCase()}`);
  }
  return `/api/download?${params.toString()}`;
}

if (form && urlInput) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const url = urlInput.value.trim();
    if (!url) {
      setStatus("Please enter a video URL first.", true);
      return;
    }
    await analyzeUrl(url);
  });
}

if (downloadVideoBtn) {
  downloadVideoBtn.addEventListener("click", () => {
    const target = buildDownloadUrl("video");
    if (!target) {
      setStatus("Analyze a URL first.", true);
      return;
    }
    window.open(target, "_blank", "noopener,noreferrer");
  });
}

if (downloadAudioBtn) {
  downloadAudioBtn.addEventListener("click", () => {
    const target = buildDownloadUrl("audio");
    if (!target) {
      setStatus("Analyze a URL first.", true);
      return;
    }
    window.open(target, "_blank", "noopener,noreferrer");
  });
}

if (audioFileFormatSelect && hasOption(audioFileFormatSelect, defaultAudioFormat)) {
  audioFileFormatSelect.value = defaultAudioFormat;
}
