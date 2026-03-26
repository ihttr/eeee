const videoUrlInput = document.getElementById("video-url");
const analyzeBtn = document.getElementById("analyze-btn");
const videoMeta = document.getElementById("video-meta");
const videoThumb = document.getElementById("video-thumb");
const videoTitle = document.getElementById("video-title");
const videoUploader = document.getElementById("video-uploader");
const videoDuration = document.getElementById("video-duration");
const formatsPanel = document.getElementById("formats-panel");
const formatSelect = document.getElementById("format-select");
const modeButtons = [...document.querySelectorAll(".mode-btn")];
const downloadBtn = document.getElementById("download-btn");
const downloadResult = document.getElementById("download-result");
const audioFormatWrap = document.getElementById("audio-format-wrap");
const audioFormatSelect = document.getElementById("audio-format-select");
const convertForm = document.getElementById("convert-form");
const convertFileInput = document.getElementById("convert-file");
const targetFormatSelect = document.getElementById("target-format");
const convertResult = document.getElementById("convert-result");
const toast = document.getElementById("toast");

let currentMode = "video";
let videoFormats = [];
let audioFormats = [];

const formatOptionsByType = {
  image: ["png", "jpg", "jpeg", "webp", "bmp", "pdf"],
  audio: ["mp3", "wav", "m4a", "aac", "flac", "ogg", "opus"],
  video: ["mp4", "mkv", "webm", "mov", "avi", "gif", "m4v"],
  pdf: ["txt"],
};

function showToast(text) {
  toast.textContent = text;
  toast.classList.remove("hidden");
  setTimeout(() => toast.classList.add("hidden"), 2600);
}

function formatSeconds(seconds) {
  if (!seconds || Number.isNaN(seconds)) {
    return "Duration: unknown";
  }
  const total = Number(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = Math.floor(total % 60);
  const pad = (num) => String(num).padStart(2, "0");
  if (h > 0) {
    return `Duration: ${h}:${pad(m)}:${pad(s)}`;
  }
  return `Duration: ${m}:${pad(s)}`;
}

function fileTypeFromExtension(ext) {
  const normalized = ext.toLowerCase();
  if (["png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff"].includes(normalized)) {
    return "image";
  }
  if (["mp3", "wav", "m4a", "aac", "flac", "ogg", "opus"].includes(normalized)) {
    return "audio";
  }
  if (["mp4", "mkv", "webm", "mov", "avi", "gif", "m4v"].includes(normalized)) {
    return "video";
  }
  if (normalized === "pdf") {
    return "pdf";
  }
  return null;
}

function setResult(target, message, isError = false) {
  target.innerHTML = "";
  const card = document.createElement("div");
  card.className = `result-card ${isError ? "error" : "success"}`;
  card.textContent = message;
  target.appendChild(card);
}

function setResultWithLink(target, prefix, url, label, isError = false) {
  target.innerHTML = "";
  const card = document.createElement("div");
  card.className = `result-card ${isError ? "error" : "success"}`;

  const prefixNode = document.createTextNode(`${prefix} `);
  const link = document.createElement("a");
  link.href = url;
  link.textContent = label;

  card.appendChild(prefixNode);
  card.appendChild(link);
  target.appendChild(card);
}

function syncModeUI() {
  modeButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === currentMode);
  });
  audioFormatWrap.classList.toggle("hidden", currentMode !== "audio");
  renderFormatSelect();
}

function renderFormatSelect() {
  const list = currentMode === "video" ? videoFormats : audioFormats;
  formatSelect.innerHTML = "";

  if (!list.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No formats found";
    formatSelect.appendChild(option);
    downloadBtn.disabled = true;
    return;
  }

  list.forEach((fmt) => {
    const option = document.createElement("option");
    option.value = fmt.id;
    option.textContent = fmt.label;
    formatSelect.appendChild(option);
  });

  downloadBtn.disabled = false;
}

analyzeBtn.addEventListener("click", async () => {
  const url = videoUrlInput.value.trim();
  if (!url) {
    showToast("Paste a video URL first.");
    return;
  }

  analyzeBtn.disabled = true;
  analyzeBtn.textContent = "Analyzing...";
  setResult(downloadResult, "Fetching stream data...", false);

  try {
    const res = await fetch("/api/video/info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || "Could not analyze this URL.");
    }

    videoFormats = data.video_formats || [];
    audioFormats = data.audio_formats || [];

    videoTitle.textContent = data.title || "Untitled";
    videoUploader.textContent = `By: ${data.uploader || "Unknown"}`;
    videoDuration.textContent = formatSeconds(data.duration);
    if (data.thumbnail) {
      videoThumb.src = data.thumbnail;
      videoThumb.classList.remove("hidden");
    } else {
      videoThumb.classList.add("hidden");
    }

    videoMeta.classList.remove("hidden");
    formatsPanel.classList.remove("hidden");
    syncModeUI();
    setResult(downloadResult, "Analysis complete. Pick a format and click download.");
  } catch (error) {
    setResult(downloadResult, error.message, true);
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "Analyze";
  }
});

modeButtons.forEach((button) => {
  button.addEventListener("click", () => {
    currentMode = button.dataset.mode;
    syncModeUI();
  });
});

downloadBtn.addEventListener("click", async () => {
  const url = videoUrlInput.value.trim();
  const formatId = formatSelect.value;
  if (!url) {
    showToast("Paste a video URL first.");
    return;
  }
  if (!formatId) {
    showToast("Pick a quality option.");
    return;
  }

  downloadBtn.disabled = true;
  downloadBtn.textContent = "Working...";
  setResult(downloadResult, "Processing your download...", false);

  try {
    const res = await fetch("/api/video/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url,
        mode: currentMode,
        format_id: formatId,
        audio_format: audioFormatSelect.value,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || "Download failed.");
    }

    setResultWithLink(downloadResult, "Done:", data.download_url, data.filename, false);
  } catch (error) {
    setResult(downloadResult, error.message, true);
  } finally {
    downloadBtn.disabled = false;
    downloadBtn.textContent = "Download";
  }
});

function updateTargetFormats() {
  const file = convertFileInput.files?.[0];
  targetFormatSelect.innerHTML = '<option value="">Select target format</option>';
  if (!file) {
    return;
  }

  const fileNameParts = file.name.split(".");
  if (fileNameParts.length < 2) {
    showToast("File needs an extension.");
    return;
  }

  const sourceExt = fileNameParts[fileNameParts.length - 1].toLowerCase();
  const type = fileTypeFromExtension(sourceExt);
  if (!type) {
    showToast("This file type is not supported yet.");
    return;
  }

  const options = formatOptionsByType[type].filter((ext) => ext !== sourceExt);
  options.forEach((ext) => {
    const option = document.createElement("option");
    option.value = ext;
    option.textContent = ext.toUpperCase();
    targetFormatSelect.appendChild(option);
  });
}

convertFileInput.addEventListener("change", updateTargetFormats);

convertForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = convertFileInput.files?.[0];
  const targetFormat = targetFormatSelect.value;

  if (!file) {
    showToast("Choose a file first.");
    return;
  }
  if (!targetFormat) {
    showToast("Pick a target format.");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  formData.append("target_format", targetFormat);

  const submitBtn = convertForm.querySelector("button[type='submit']");
  submitBtn.disabled = true;
  submitBtn.textContent = "Converting...";
  setResult(convertResult, "Converting file...", false);

  try {
    const res = await fetch("/api/convert", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || "Conversion failed.");
    }
    setResultWithLink(convertResult, "Done:", data.download_url, data.filename, false);
  } catch (error) {
    setResult(convertResult, error.message, true);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Convert";
  }
});
