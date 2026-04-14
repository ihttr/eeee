from __future__ import annotations

import json
import logging
import os
import re
import shutil
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import yt_dlp
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.background import BackgroundTask

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TMP_DIR = BASE_DIR / ".tmp_downloads"
TMP_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_FILE = TMP_DIR / "history.json"
FAILURES_FILE = TMP_DIR / "failures.json"
HISTORY_LOCK = threading.Lock()
MAX_HISTORY_ITEMS = 300
MAX_FAILURE_ITEMS = 500
SUPPORTED_ROUTE_LANGS = {"en", "ar"}
APP_START_TS = time.time()

logger = logging.getLogger("media_downloader")

SENTRY_ENABLED = False
sentry_sdk = None
_sentry_dsn = os.getenv("SENTRY_DSN", "").strip()
if _sentry_dsn:
    try:
        import sentry_sdk as _sentry

        _sample_rate_raw = os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0").strip() or "0.0"
        _sample_rate = float(_sample_rate_raw)
        _sentry.init(
            dsn=_sentry_dsn,
            traces_sample_rate=_sample_rate,
            environment=os.getenv("SENTRY_ENV", "production"),
        )
        sentry_sdk = _sentry
        SENTRY_ENABLED = True
    except Exception as exc:
        logger.exception("Failed to initialize Sentry: %s", exc)

app = FastAPI(title="Media Downloader", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class InfoRequest(BaseModel):
    url: str
    source_page: str | None = None


def _validate_url(url: str) -> str:
    candidate = url.strip()
    if not re.match(r"^https?://", candidate, flags=re.IGNORECASE):
        raise HTTPException(status_code=400, detail="Only http/https URLs are allowed.")
    return candidate


def _as_megabytes(size: int | None) -> str | None:
    if not size:
        return None
    return f"{size / (1024 * 1024):.1f} MB"


def _clean_name(name: str) -> str:
    cleaned = re.sub(r"[^\w\-. ]+", "", name, flags=re.ASCII).strip()
    return cleaned[:120] or "download"


def _extract_info(url: str) -> dict[str, Any]:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not isinstance(info, dict):
        raise HTTPException(status_code=400, detail="Could not read media information.")
    if info.get("_type") == "playlist":
        entries = info.get("entries") or []
        first = next((entry for entry in entries if entry), None)
        if not first:
            raise HTTPException(status_code=400, detail="Playlist has no downloadable entries.")
        return first
    return info


def _video_options(formats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    for fmt in formats:
        format_id = fmt.get("format_id")
        if not format_id or format_id in seen:
            continue
        if fmt.get("vcodec") == "none" or fmt.get("acodec") == "none":
            continue

        seen.add(format_id)
        height = fmt.get("height")
        fps = fmt.get("fps")
        ext = str(fmt.get("ext", "mp4")).upper()
        size = fmt.get("filesize") or fmt.get("filesize_approx")

        label_parts = []
        label_parts.append(f"{height}p" if height else "Unknown quality")
        label_parts.append(ext)
        if fps and int(fps) > 30:
            label_parts.append(f"{int(fps)}fps")
        size_label = _as_megabytes(size)
        if size_label:
            label_parts.append(size_label)

        items.append(
            {
                "format_id": format_id,
                "height": int(height or 0),
                "ext": str(fmt.get("ext", "mp4")),
                "filesize": int(size or 0),
                "label": " | ".join(label_parts),
            }
        )

    items.sort(key=lambda x: (x["height"], x["filesize"]), reverse=True)
    return [{"format_id": "best", "label": "Best available (auto)"}] + [
        {"format_id": f["format_id"], "label": f["label"]} for f in items
    ]


def _audio_options(formats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    for fmt in formats:
        format_id = fmt.get("format_id")
        if not format_id or format_id in seen:
            continue
        if fmt.get("acodec") == "none" or fmt.get("vcodec") != "none":
            continue

        seen.add(format_id)
        abr = fmt.get("abr")
        ext = str(fmt.get("ext", "m4a")).upper()
        size = fmt.get("filesize") or fmt.get("filesize_approx")

        label_parts = []
        label_parts.append(f"{int(abr)} kbps" if abr else "Audio")
        label_parts.append(ext)
        size_label = _as_megabytes(size)
        if size_label:
            label_parts.append(size_label)

        items.append(
            {
                "format_id": format_id,
                "abr": float(abr or 0),
                "filesize": int(size or 0),
                "label": " | ".join(label_parts),
            }
        )

    items.sort(key=lambda x: (x["abr"], x["filesize"]), reverse=True)
    return [{"format_id": "bestaudio", "label": "Best audio (auto)"}] + [
        {"format_id": f["format_id"], "label": f["label"]} for f in items
    ]


def _latest_file(path: Path) -> Path:
    files = [p for p in path.glob("*") if p.is_file()]
    if not files:
        raise HTTPException(status_code=500, detail="Download finished, but file was not found.")
    return max(files, key=lambda p: p.stat().st_size)


def _read_history_nolock() -> list[dict[str, Any]]:
    return _read_json_list_nolock(HISTORY_FILE)


def _write_history_nolock(items: list[dict[str, Any]]) -> None:
    _write_json_list_nolock(HISTORY_FILE, items)


def _append_history_entry(entry: dict[str, Any]) -> None:
    with HISTORY_LOCK:
        _append_item_nolock(HISTORY_FILE, MAX_HISTORY_ITEMS, entry)


def _read_failures_nolock() -> list[dict[str, Any]]:
    return _read_json_list_nolock(FAILURES_FILE)


def _append_failure_entry(entry: dict[str, Any]) -> None:
    with HISTORY_LOCK:
        _append_item_nolock(FAILURES_FILE, MAX_FAILURE_ITEMS, entry)


def _download_url_from_entry(entry: dict[str, Any]) -> str:
    params = {
        "url": str(entry.get("source_url") or ""),
        "kind": str(entry.get("kind") or "video"),
        "format_id": str(entry.get("format_id") or "best"),
    }
    if params["kind"] == "audio":
        params["audio_format"] = str(entry.get("audio_format") or "mp3")
    return f"/api/download?{urlencode(params)}"


def _history_response_item(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entry.get("id"),
        "title": entry.get("title") or "Untitled media",
        "source_url": entry.get("source_url"),
        "kind": entry.get("kind") or "video",
        "format": entry.get("format") or "Auto",
        "created_at": entry.get("created_at"),
        "download_url": _download_url_from_entry(entry),
        "source_page": entry.get("source_page"),
        "client_ip": entry.get("client_ip"),
        "user_agent": entry.get("user_agent"),
    }


def _failure_response_item(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entry.get("id"),
        "source_url": entry.get("source_url"),
        "kind": entry.get("kind") or "video",
        "format_id": entry.get("format_id") or "best",
        "audio_format": entry.get("audio_format"),
        "created_at": entry.get("created_at"),
        "source_page": entry.get("source_page"),
        "client_ip": entry.get("client_ip"),
        "user_agent": entry.get("user_agent"),
        "stage": entry.get("stage") or "download",
        "error": entry.get("error") or "Unknown error",
    }


def _uptime_seconds() -> int:
    return int(time.time() - APP_START_TS)


def _monitoring_snapshot_nolock() -> dict[str, Any]:
    history = _read_history_nolock()
    failures = _read_failures_nolock()
    latest_failure = failures[0] if failures else None
    return {
        "status": "ok",
        "uptime_seconds": _uptime_seconds(),
        "sentry_enabled": SENTRY_ENABLED,
        "downloads_total": len(history),
        "downloads_video": sum(1 for x in history if x.get("kind") == "video"),
        "downloads_audio": sum(1 for x in history if x.get("kind") == "audio"),
        "failures_total": len(failures),
        "latest_failure": _failure_response_item(latest_failure) if latest_failure else None,
    }


def _failure_entry(
    request: Request,
    *,
    url: str,
    kind: str,
    format_id: str,
    audio_format: str,
    source_page: str | None,
    stage: str,
    error_message: str,
) -> dict[str, Any]:
    return {
        "id": uuid.uuid4().hex,
        "source_url": url,
        "kind": kind,
        "format_id": format_id or ("bestaudio" if kind == "audio" else "best"),
        "audio_format": audio_format if kind == "audio" else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_page": (source_page or "unknown")[:80],
        "client_ip": _client_ip(request),
        "user_agent": (request.headers.get("user-agent") or "unknown")[:240],
        "stage": stage[:40],
        "error": (error_message or "Unknown error")[:600],
    }


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded[:80]
    if request.client and request.client.host:
        return request.client.host[:80]
    return "unknown"


def _capture_exception(exc: Exception) -> None:
    if SENTRY_ENABLED and sentry_sdk is not None:
        try:
            sentry_sdk.capture_exception(exc)
        except Exception:
            pass


def _read_json_list_nolock(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    return [entry for entry in raw if isinstance(entry, dict)]


def _write_json_list_nolock(path: Path, items: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(items, ensure_ascii=True), encoding="utf-8")


def _append_item_nolock(path: Path, limit: int, entry: dict[str, Any]) -> None:
    items = _read_json_list_nolock(path)
    items.insert(0, entry)
    _write_json_list_nolock(path, items[:limit])


def _page_slug_from_template(name: str) -> str:
    mapping = {
        "index.html": "",
        "instagram-downloader.html": "instagram-downloader",
        "youtube-downloader.html": "youtube-downloader",
        "tiktok-downloader.html": "tiktok-downloader",
        "twitter-downloader.html": "twitter-downloader",
        "video-to-mp3.html": "video-to-mp3",
        "dashboard.html": "dashboard",
        "owner-dashboard.html": "owner-dashboard",
    }
    return mapping.get(name, "")


def _canonical_paths_for_slug(slug: str) -> tuple[str, str, str]:
    default_path = "/" if not slug else f"/{slug}"
    en_path = "/en" if not slug else f"/en/{slug}"
    ar_path = "/ar" if not slug else f"/ar/{slug}"
    return default_path, en_path, ar_path


def _inject_seo_links(html: str, base: str, slug: str, lang: str | None) -> str:
    default_path, en_path, ar_path = _canonical_paths_for_slug(slug)
    canonical_path = ar_path if lang == "ar" else en_path
    seo_tags = "\n".join(
        [
            f'<link rel="canonical" href="{base}{canonical_path}" />',
            f'<link rel="alternate" hreflang="en" href="{base}{en_path}" />',
            f'<link rel="alternate" hreflang="ar" href="{base}{ar_path}" />',
            f'<link rel="alternate" hreflang="x-default" href="{base}{default_path}" />',
        ]
    )
    if "</head>" in html:
        return html.replace("</head>", f"  {seo_tags}\n</head>", 1)
    return html


def _render_page_html(name: str, request: Request, lang: str | None = None) -> HTMLResponse:
    resolved_lang = (lang or "").lower().strip() or None
    if resolved_lang and resolved_lang not in SUPPORTED_ROUTE_LANGS:
        resolved_lang = "en"

    html = (STATIC_DIR / name).read_text(encoding="utf-8")
    html_lang = resolved_lang or "en"
    html = re.sub(r"<html lang=\"[^\"]+\">", f"<html lang=\"{html_lang}\">", html, count=1)

    def body_replacer(match: re.Match[str]) -> str:
        attrs = match.group(1)
        if 'data-default-lang="' in attrs:
            attrs = re.sub(r'data-default-lang="[^"]+"', f'data-default-lang="{html_lang}"', attrs, count=1)
        else:
            attrs = f'{attrs} data-default-lang="{html_lang}"'
        return f"<body{attrs}>"

    html = re.sub(r"<body([^>]*)>", body_replacer, html, count=1)

    if resolved_lang:
        internal_paths = [
            "/",
            "/dashboard",
            "/owner-dashboard",
            "/instagram-downloader",
            "/youtube-downloader",
            "/tiktok-downloader",
            "/twitter-downloader",
            "/video-to-mp3",
        ]
        for path in internal_paths:
            localized_target = f"/{resolved_lang}" if path == "/" else f"/{resolved_lang}{path}"
            html = html.replace(f'href="{path}"', f'href="{localized_target}"')

    base = str(request.base_url).rstrip("/")
    html = _inject_seo_links(html, base, _page_slug_from_template(name), resolved_lang)
    return HTMLResponse(content=html)


def _page_file(name: str) -> FileResponse:
    return FileResponse(STATIC_DIR / name)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/detailed")
def health_detailed() -> dict[str, Any]:
    with HISTORY_LOCK:
        return _monitoring_snapshot_nolock()


@app.get("/uptime")
def uptime() -> dict[str, Any]:
    return {"status": "ok", "uptime_seconds": _uptime_seconds()}


@app.get("/")
def root(request: Request) -> HTMLResponse:
    return _render_page_html("index.html", request)


@app.get("/favicon.ico")
def favicon() -> FileResponse:
    return _page_file("favicon.ico")


@app.get("/instagram-downloader")
@app.get("/instagram-downloader/")
def instagram_downloader(request: Request) -> HTMLResponse:
    return _render_page_html("instagram-downloader.html", request)


@app.get("/youtube-downloader")
@app.get("/youtube-downloader/")
def youtube_downloader(request: Request) -> HTMLResponse:
    return _render_page_html("youtube-downloader.html", request)


@app.get("/tiktok-downloader")
@app.get("/tiktok-downloader/")
def tiktok_downloader(request: Request) -> HTMLResponse:
    return _render_page_html("tiktok-downloader.html", request)


@app.get("/twitter-downloader")
@app.get("/twitter-downloader/")
def twitter_downloader(request: Request) -> HTMLResponse:
    return _render_page_html("twitter-downloader.html", request)


@app.get("/video-to-mp3")
@app.get("/video-to-mp3/")
def video_to_mp3(request: Request) -> HTMLResponse:
    return _render_page_html("video-to-mp3.html", request)


@app.get("/dashboard")
@app.get("/dashboard/")
def dashboard(request: Request) -> HTMLResponse:
    return _render_page_html("dashboard.html", request)


@app.get("/owner-dashboard")
@app.get("/owner-dashboard/")
def owner_dashboard(request: Request) -> HTMLResponse:
    return _render_page_html("owner-dashboard.html", request)


@app.get("/en")
@app.get("/en/")
def english_home(request: Request) -> HTMLResponse:
    return _render_page_html("index.html", request, "en")


@app.get("/ar")
@app.get("/ar/")
def arabic_home(request: Request) -> HTMLResponse:
    return _render_page_html("index.html", request, "ar")


@app.get("/en/instagram-downloader")
@app.get("/en/instagram-downloader/")
def english_instagram(request: Request) -> HTMLResponse:
    return _render_page_html("instagram-downloader.html", request, "en")


@app.get("/ar/instagram-downloader")
@app.get("/ar/instagram-downloader/")
def arabic_instagram(request: Request) -> HTMLResponse:
    return _render_page_html("instagram-downloader.html", request, "ar")


@app.get("/en/youtube-downloader")
@app.get("/en/youtube-downloader/")
def english_youtube(request: Request) -> HTMLResponse:
    return _render_page_html("youtube-downloader.html", request, "en")


@app.get("/ar/youtube-downloader")
@app.get("/ar/youtube-downloader/")
def arabic_youtube(request: Request) -> HTMLResponse:
    return _render_page_html("youtube-downloader.html", request, "ar")


@app.get("/en/tiktok-downloader")
@app.get("/en/tiktok-downloader/")
def english_tiktok(request: Request) -> HTMLResponse:
    return _render_page_html("tiktok-downloader.html", request, "en")


@app.get("/ar/tiktok-downloader")
@app.get("/ar/tiktok-downloader/")
def arabic_tiktok(request: Request) -> HTMLResponse:
    return _render_page_html("tiktok-downloader.html", request, "ar")


@app.get("/en/twitter-downloader")
@app.get("/en/twitter-downloader/")
def english_twitter(request: Request) -> HTMLResponse:
    return _render_page_html("twitter-downloader.html", request, "en")


@app.get("/ar/twitter-downloader")
@app.get("/ar/twitter-downloader/")
def arabic_twitter(request: Request) -> HTMLResponse:
    return _render_page_html("twitter-downloader.html", request, "ar")


@app.get("/en/video-to-mp3")
@app.get("/en/video-to-mp3/")
def english_mp3(request: Request) -> HTMLResponse:
    return _render_page_html("video-to-mp3.html", request, "en")


@app.get("/ar/video-to-mp3")
@app.get("/ar/video-to-mp3/")
def arabic_mp3(request: Request) -> HTMLResponse:
    return _render_page_html("video-to-mp3.html", request, "ar")


@app.get("/en/dashboard")
@app.get("/en/dashboard/")
def english_dashboard(request: Request) -> HTMLResponse:
    return _render_page_html("dashboard.html", request, "en")


@app.get("/ar/dashboard")
@app.get("/ar/dashboard/")
def arabic_dashboard(request: Request) -> HTMLResponse:
    return _render_page_html("dashboard.html", request, "ar")


@app.get("/en/owner-dashboard")
@app.get("/en/owner-dashboard/")
def english_owner_dashboard(request: Request) -> HTMLResponse:
    return _render_page_html("owner-dashboard.html", request, "en")


@app.get("/ar/owner-dashboard")
@app.get("/ar/owner-dashboard/")
def arabic_owner_dashboard(request: Request) -> HTMLResponse:
    return _render_page_html("owner-dashboard.html", request, "ar")


def _build_urlset_xml(base: str, paths: list[str], priority: str = "0.8") -> str:
    lastmod = datetime.now(timezone.utc).date().isoformat()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path in paths:
        lines.append("  <url>")
        lines.append(f"    <loc>{base}{path}</loc>")
        lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append("    <changefreq>daily</changefreq>")
        lines.append(f"    <priority>{priority}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines)


@app.get("/sitemap.xml")
@app.get("/sitmap.xml")
def sitemap_index(request: Request) -> Response:
    base = str(request.base_url).rstrip("/")
    lastmod = datetime.now(timezone.utc).date().isoformat()
    sitemaps = ["/sitemap-core.xml", "/sitemap-en.xml", "/sitemap-ar.xml"]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for item in sitemaps:
        lines.append("  <sitemap>")
        lines.append(f"    <loc>{base}{item}</loc>")
        lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append("  </sitemap>")
    lines.append("</sitemapindex>")
    return Response(content="\n".join(lines), media_type="application/xml")


@app.get("/sitemap-core.xml")
def sitemap_core(request: Request) -> Response:
    base = str(request.base_url).rstrip("/")
    paths = [
        "/",
        "/instagram-downloader",
        "/youtube-downloader",
        "/tiktok-downloader",
        "/twitter-downloader",
        "/video-to-mp3",
    ]
    return Response(content=_build_urlset_xml(base, paths, "0.8"), media_type="application/xml")


@app.get("/sitemap-en.xml")
def sitemap_en(request: Request) -> Response:
    base = str(request.base_url).rstrip("/")
    paths = [
        "/en",
        "/en/instagram-downloader",
        "/en/youtube-downloader",
        "/en/tiktok-downloader",
        "/en/twitter-downloader",
        "/en/video-to-mp3",
        
    ]
    return Response(content=_build_urlset_xml(base, paths, "0.7"), media_type="application/xml")


@app.get("/sitemap-ar.xml")
def sitemap_ar(request: Request) -> Response:
    base = str(request.base_url).rstrip("/")
    paths = [
        "/ar",
        "/ar/instagram-downloader",
        "/ar/youtube-downloader",
        "/ar/tiktok-downloader",
        "/ar/twitter-downloader",
        "/ar/video-to-mp3",
        
    ]
    return Response(content=_build_urlset_xml(base, paths, "0.7"), media_type="application/xml")


@app.get("/robots.txt")
def robots(request: Request) -> Response:
    base = str(request.base_url).rstrip("/")
    content = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /owner-dashboard",
            "Disallow: /en/owner-dashboard",
            "Disallow: /ar/owner-dashboard",
            f"Sitemap: {base}/sitemap.xml",
        ]
    )
    return Response(content=content, media_type="text/plain")


@app.get("/api/history")
def history_list() -> dict[str, list[dict[str, Any]]]:
    with HISTORY_LOCK:
        items = _read_history_nolock()
    return {"items": [_history_response_item(item) for item in items]}


@app.delete("/api/history")
def history_clear() -> dict[str, str]:
    with HISTORY_LOCK:
        _write_history_nolock([])
    return {"status": "cleared"}


@app.get("/api/failures")
def failures_list() -> dict[str, list[dict[str, Any]]]:
    with HISTORY_LOCK:
        items = _read_failures_nolock()
    return {"items": [_failure_response_item(item) for item in items]}


@app.delete("/api/failures")
def failures_clear() -> dict[str, str]:
    with HISTORY_LOCK:
        _write_json_list_nolock(FAILURES_FILE, [])
    return {"status": "cleared"}


@app.get("/api/monitoring")
def monitoring_summary() -> dict[str, Any]:
    with HISTORY_LOCK:
        return _monitoring_snapshot_nolock()


@app.post("/api/info")
def media_info(payload: InfoRequest, request: Request) -> dict[str, Any]:
    source_url = _validate_url(payload.url)
    try:
        info = _extract_info(source_url)
    except HTTPException:
        raise
    except Exception as exc:
        _append_failure_entry(
            _failure_entry(
                request,
                url=source_url,
                kind="video",
                format_id="best",
                audio_format="mp3",
                source_page=payload.source_page,
                stage="analyze",
                error_message=str(exc),
            )
        )
        _capture_exception(exc)
        raise HTTPException(status_code=400, detail=f"Failed to analyze URL: {exc}") from exc

    formats = info.get("formats") or []
    if not isinstance(formats, list):
        formats = []

    return {
        "title": info.get("title") or "Untitled media",
        "uploader": info.get("uploader") or info.get("channel") or "Unknown",
        "duration": info.get("duration"),
        "thumbnail": info.get("thumbnail"),
        "source_url": source_url,
        "video_options": _video_options(formats),
        "audio_options": _audio_options(formats),
    }


@app.get("/api/download")
def download(
    request: Request,
    url: str,
    kind: str = "video",
    format_id: str = "best",
    audio_format: str = "mp3",
    format_label: str | None = None,
    source_page: str | None = None,
) -> FileResponse:
    url = _validate_url(url)
    kind = kind.lower().strip()
    audio_format = audio_format.lower().strip()
    if kind not in {"video", "audio"}:
        raise HTTPException(status_code=400, detail="kind must be video or audio")
    if audio_format not in {"mp3", "m4a", "wav", "opus"}:
        raise HTTPException(status_code=400, detail="Unsupported audio format.")

    work_dir = TMP_DIR / uuid.uuid4().hex
    work_dir.mkdir(parents=True, exist_ok=True)

    outtmpl = str(work_dir / "%(title).80s [%(id)s].%(ext)s")
    ydl_opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "outtmpl": outtmpl,
    }

    if kind == "video":
        ydl_opts["format"] = format_id or "best"
        ydl_opts["merge_output_format"] = "mp4"
    else:
        selected_audio = format_id if format_id and format_id != "best" else "bestaudio"
        ydl_opts["format"] = f"{selected_audio}/bestaudio/best"
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": audio_format,
                "preferredquality": "192",
            }
        ]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as exc:
        _append_failure_entry(
            _failure_entry(
                request,
                url=url,
                kind=kind,
                format_id=format_id,
                audio_format=audio_format,
                source_page=source_page,
                stage="download",
                error_message=str(exc),
            )
        )
        _capture_exception(exc)
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Download failed: {exc}") from exc

    try:
        file_path = _latest_file(work_dir)
    except HTTPException as exc:
        _append_failure_entry(
            _failure_entry(
                request,
                url=url,
                kind=kind,
                format_id=format_id,
                audio_format=audio_format,
                source_page=source_page,
                stage="postprocess",
                error_message=str(exc.detail),
            )
        )
        shutil.rmtree(work_dir, ignore_errors=True)
        raise
    title = "download"
    if isinstance(info, dict):
        title = str(info.get("title") or title)
    filename = f"{_clean_name(title)}{file_path.suffix or ''}"
    display_format = (format_label or "").strip()
    if not display_format:
        if kind == "video":
            display_format = format_id or "best"
        else:
            selected_audio = format_id if format_id and format_id != "best" else "bestaudio"
            display_format = f"{selected_audio} -> {audio_format.upper()}"
    _append_history_entry(
        {
            "id": uuid.uuid4().hex,
            "title": title,
            "source_url": url,
            "kind": kind,
            "format_id": format_id or ("bestaudio" if kind == "audio" else "best"),
            "audio_format": audio_format if kind == "audio" else None,
            "format": display_format[:180],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_page": (source_page or "unknown")[:80],
            "client_ip": _client_ip(request),
            "user_agent": (request.headers.get("user-agent") or "unknown")[:240],
        }
    )

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream",
        background=BackgroundTask(shutil.rmtree, work_dir, ignore_errors=True),
    )
