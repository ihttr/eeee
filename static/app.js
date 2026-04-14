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
const allowedHosts = (document.body.dataset.allowedHosts || "")
  .split(",")
  .map((x) => x.trim().toLowerCase())
  .filter(Boolean);

let currentInfo = null;
const routeDefaultLang = (document.body.dataset.defaultLang || "").toLowerCase();
let currentLang = routeDefaultLang || localStorage.getItem("site_lang") || "en";

const i18n = {
  en: {
    analyze: "Analyze",
    analyzing: "Analyzing...",
    reading: "Reading video details...",
    ready: "Ready. Choose your options and download.",
    readyAudio: "Ready. Choose audio stream and download.",
    needUrl: "Please enter a video URL first.",
    needAnalyze: "Analyze a URL first.",
    wrongHost: "This page supports only its own platform links.",
    genericErr: "Something went wrong.",
    downloadVideo: "Download Video",
    downloadAudio: "Download Audio",
  },
  ar: {
    analyze: "تحليل",
    analyzing: "جاري التحليل...",
    reading: "جاري قراءة تفاصيل الفيديو...",
    ready: "جاهز. اختر الإعدادات وابدأ التنزيل.",
    readyAudio: "جاهز. اختر مسار الصوت وابدأ التنزيل.",
    needUrl: "الرجاء إدخال رابط فيديو أولاً.",
    needAnalyze: "قم بتحليل الرابط أولاً.",
    wrongHost: "هذه الصفحة مخصصة للمنصة الخاصة بها فقط.",
    genericErr: "حدث خطأ ما.",
    downloadVideo: "تنزيل الفيديو",
    downloadAudio: "تنزيل الصوت",
  },
  es: {
    analyze: "Analizar",
    analyzing: "Analizando...",
    reading: "Leyendo detalles del video...",
    ready: "Listo. Elige opciones y descarga.",
    readyAudio: "Listo. Elige flujo de audio y descarga.",
    needUrl: "Primero ingresa un enlace de video.",
    needAnalyze: "Primero analiza un enlace.",
    wrongHost: "Esta pagina solo admite enlaces de su plataforma.",
    genericErr: "Algo salio mal.",
    downloadVideo: "Descargar Video",
    downloadAudio: "Descargar Audio",
  },
  fr: {
    analyze: "Analyser",
    analyzing: "Analyse en cours...",
    reading: "Lecture des details de la video...",
    ready: "Pret. Choisissez les options et telechargez.",
    readyAudio: "Pret. Choisissez le flux audio et telechargez.",
    needUrl: "Veuillez entrer un lien video d'abord.",
    needAnalyze: "Analysez un lien d'abord.",
    wrongHost: "Cette page accepte uniquement les liens de sa plateforme.",
    genericErr: "Une erreur est survenue.",
    downloadVideo: "Telecharger Video",
    downloadAudio: "Telecharger Audio",
  },
  pt: {
    analyze: "Analisar",
    analyzing: "Analisando...",
    reading: "Lendo detalhes do video...",
    ready: "Pronto. Escolha as opcoes e baixe.",
    readyAudio: "Pronto. Escolha o fluxo de audio e baixe.",
    needUrl: "Insira primeiro um link de video.",
    needAnalyze: "Analise um link primeiro.",
    wrongHost: "Esta pagina aceita apenas links da propria plataforma.",
    genericErr: "Algo deu errado.",
    downloadVideo: "Baixar Video",
    downloadAudio: "Baixar Audio",
  },
  hi: {
    analyze: "विश्लेषण करें",
    analyzing: "विश्लेषण हो रहा है...",
    reading: "वीडियो विवरण पढ़ा जा रहा है...",
    ready: "तैयार है। विकल्प चुनें और डाउनलोड करें।",
    readyAudio: "तैयार है। ऑडियो स्ट्रीम चुनें और डाउनलोड करें।",
    needUrl: "पहले वीडियो लिंक डालें।",
    needAnalyze: "पहले लिंक का विश्लेषण करें।",
    wrongHost: "यह पेज केवल अपनी प्लेटफॉर्म लिंक के लिए है।",
    genericErr: "कुछ गलत हो गया।",
    downloadVideo: "वीडियो डाउनलोड करें",
    downloadAudio: "ऑडियो डाउनलोड करें",
  },
  zh: {
    analyze: "分析",
    analyzing: "正在分析...",
    reading: "正在读取视频详情...",
    ready: "准备好了。请选择选项并下载。",
    readyAudio: "准备好了。请选择音频流并下载。",
    needUrl: "请先输入视频链接。",
    needAnalyze: "请先分析链接。",
    wrongHost: "此页面仅支持其对应平台的链接。",
    genericErr: "发生错误。",
    downloadVideo: "下载视频",
    downloadAudio: "下载音频",
  },
  ru: {
    analyze: "Анализ",
    analyzing: "Анализируем...",
    reading: "Читаем данные видео...",
    ready: "Готово. Выберите параметры и скачайте.",
    readyAudio: "Готово. Выберите аудиопоток и скачайте.",
    needUrl: "Сначала вставьте ссылку на видео.",
    needAnalyze: "Сначала проанализируйте ссылку.",
    wrongHost: "Эта страница поддерживает только ссылки своей платформы.",
    genericErr: "Что-то пошло не так.",
    downloadVideo: "Скачать видео",
    downloadAudio: "Скачать аудио",
  },
  de: {
    analyze: "Analysieren",
    analyzing: "Wird analysiert...",
    reading: "Videodetails werden gelesen...",
    ready: "Fertig. Optionen waehlen und herunterladen.",
    readyAudio: "Fertig. Audiostream waehlen und herunterladen.",
    needUrl: "Bitte zuerst einen Videolink eingeben.",
    needAnalyze: "Bitte zuerst den Link analysieren.",
    wrongHost: "Diese Seite erlaubt nur Links der eigenen Plattform.",
    genericErr: "Etwas ist schiefgelaufen.",
    downloadVideo: "Video herunterladen",
    downloadAudio: "Audio herunterladen",
  },
  id: {
    analyze: "Analisis",
    analyzing: "Sedang menganalisis...",
    reading: "Membaca detail video...",
    ready: "Siap. Pilih opsi dan unduh.",
    readyAudio: "Siap. Pilih stream audio dan unduh.",
    needUrl: "Masukkan tautan video terlebih dahulu.",
    needAnalyze: "Analisis tautan terlebih dahulu.",
    wrongHost: "Halaman ini hanya mendukung tautan platformnya sendiri.",
    genericErr: "Terjadi kesalahan.",
    downloadVideo: "Unduh Video",
    downloadAudio: "Unduh Audio",
  },
  tr: {
    analyze: "Analiz Et",
    analyzing: "Analiz ediliyor...",
    reading: "Video ayrintilari okunuyor...",
    ready: "Hazir. Secenekleri belirleyip indirin.",
    readyAudio: "Hazir. Ses akisını secip indirin.",
    needUrl: "Lutfen once bir video baglantisi girin.",
    needAnalyze: "Lutfen once baglantiyi analiz edin.",
    wrongHost: "Bu sayfa sadece kendi platform baglantilarini destekler.",
    genericErr: "Bir hata olustu.",
    downloadVideo: "Videoyu Indir",
    downloadAudio: "Sesi Indir",
  },
  ja: {
    analyze: "解析",
    analyzing: "解析中...",
    reading: "動画の詳細を取得中...",
    ready: "準備完了。オプションを選んでダウンロードしてください。",
    readyAudio: "準備完了。音声ストリームを選んでダウンロードしてください。",
    needUrl: "先に動画URLを入力してください。",
    needAnalyze: "先にURLを解析してください。",
    wrongHost: "このページは対応プラットフォームのリンクのみ利用できます。",
    genericErr: "エラーが発生しました。",
    downloadVideo: "動画をダウンロード",
    downloadAudio: "音声をダウンロード",
  },
};

function t(key) {
  return (i18n[currentLang] || i18n.en)[key] || i18n.en[key] || key;
}

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
  analyzeBtn.textContent = loading ? t("analyzing") : t("analyze");
}

function applyDefaultsAfterAnalyze() {
  if (audioFileFormatSelect && hasOption(audioFileFormatSelect, defaultAudioFormat)) {
    audioFileFormatSelect.value = defaultAudioFormat;
  }
}

async function analyzeUrl(url) {
  setLoading(true);
  setStatus(t("reading"));
  if (resultSection) resultSection.classList.add("hidden");
  currentInfo = null;

  try {
    const response = await fetch("/api/info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, source_page: window.location.pathname || "/" }),
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
      setStatus(t("readyAudio"));
    } else {
      setStatus(t("ready"));
    }
  } catch (err) {
    setStatus(err.message || t("genericErr"), true);
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
  params.set("source_page", window.location.pathname || "/");
  return `/api/download?${params.toString()}`;
}

function isHostAllowed(inputUrl) {
  if (!allowedHosts.length) return true;
  try {
    const u = new URL(inputUrl);
    const host = u.hostname.toLowerCase();
    return allowedHosts.some((allowed) => host === allowed || host.endsWith(`.${allowed}`));
  } catch {
    return false;
  }
}

function applyLanguage() {
  if (analyzeBtn) analyzeBtn.textContent = t("analyze");
  if (downloadVideoBtn) downloadVideoBtn.textContent = t("downloadVideo");
  if (downloadAudioBtn) downloadAudioBtn.textContent = t("downloadAudio");
  document.documentElement.setAttribute("lang", currentLang);
  document.documentElement.setAttribute("dir", currentLang === "ar" ? "rtl" : "ltr");
}

function mountLanguageSelector() {
  const hero = document.querySelector(".hero");
  if (!hero) return;
  const wrap = document.createElement("div");
  wrap.className = "lang-wrap";
  wrap.innerHTML = `
    <label class="lang-label" for="lang-select">Language</label>
    <select id="lang-select" class="lang-select">
      <option value="en">English</option>
      <option value="ar">العربية</option>
      <option value="es">Español</option>
      <option value="fr">Français</option>
      <option value="pt">Português</option>
      <option value="hi">हिन्दी</option>
      <option value="zh">中文</option>
      <option value="ru">Русский</option>
      <option value="de">Deutsch</option>
      <option value="id">Bahasa Indonesia</option>
      <option value="tr">Türkçe</option>
      <option value="ja">日本語</option>
    </select>
  `;
  hero.prepend(wrap);
  const select = wrap.querySelector("#lang-select");
  if (!i18n[currentLang]) currentLang = "en";
  select.value = currentLang;
  select.addEventListener("change", () => {
    currentLang = select.value;
    localStorage.setItem("site_lang", currentLang);
    applyLanguage();
  });
}

if (form && urlInput) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const url = urlInput.value.trim();
    if (!url) {
      setStatus(t("needUrl"), true);
      return;
    }
    if (!isHostAllowed(url)) {
      setStatus(t("wrongHost"), true);
      return;
    }
    await analyzeUrl(url);
  });
}

if (downloadVideoBtn) {
  downloadVideoBtn.addEventListener("click", () => {
    const target = buildDownloadUrl("video");
    if (!target) {
      setStatus(t("needAnalyze"), true);
      return;
    }
    window.open(target, "_blank", "noopener,noreferrer");
  });
}

if (downloadAudioBtn) {
  downloadAudioBtn.addEventListener("click", () => {
    const target = buildDownloadUrl("audio");
    if (!target) {
      setStatus(t("needAnalyze"), true);
      return;
    }
    window.open(target, "_blank", "noopener,noreferrer");
  });
}

if (audioFileFormatSelect && hasOption(audioFileFormatSelect, defaultAudioFormat)) {
  audioFileFormatSelect.value = defaultAudioFormat;
}

mountLanguageSelector();
applyLanguage();
