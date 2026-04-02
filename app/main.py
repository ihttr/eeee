from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path
from typing import Any

import yt_dlp
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.background import BackgroundTask

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TMP_DIR = BASE_DIR / ".tmp_downloads"
TMP_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Media Downloader", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class InfoRequest(BaseModel):
    url: str


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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/dashboard")
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "dashboard.html")
    
    
@app.post("/api/info")
def media_info(payload: InfoRequest) -> dict[str, Any]:
    source_url = _validate_url(payload.url)
    try:
        info = _extract_info(source_url)
    except HTTPException:
        raise
    except Exception as exc:
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
    url: str,
    kind: str = "video",
    format_id: str = "best",
    audio_format: str = "mp3",
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
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Download failed: {exc}") from exc

    try:
        file_path = _latest_file(work_dir)
    except HTTPException:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise
    title = "download"
    if isinstance(info, dict):
        title = str(info.get("title") or title)
    filename = f"{_clean_name(title)}{file_path.suffix or ''}"

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream",
        background=BackgroundTask(shutil.rmtree, work_dir, ignore_errors=True),
    )
