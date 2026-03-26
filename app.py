from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import uuid
from pathlib import Path
from typing import Any

from flask import Flask, abort, jsonify, render_template, request, send_from_directory
# from PIL import Image
# from pypdf import PdfReader

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = Path(os.getenv("MEDIA_FORGE_STORAGE_DIR", str(BASE_DIR / "workspace")))
UPLOAD_DIR = WORKSPACE_DIR / "uploads"
DOWNLOAD_DIR = WORKSPACE_DIR / "downloads"
CONVERTED_DIR = WORKSPACE_DIR / "converted"

for directory in (UPLOAD_DIR, DOWNLOAD_DIR, CONVERTED_DIR):
    directory.mkdir(parents=True, exist_ok=True)

IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff"}
AUDIO_EXTENSIONS = {"mp3", "wav", "m4a", "aac", "flac", "ogg", "opus"}
VIDEO_EXTENSIONS = {"mp4", "mkv", "webm", "mov", "avi", "m4v", "gif"}
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | VIDEO_EXTENSIONS

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024


def run_command(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            cmd,
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        binary = cmd[0]
        raise RuntimeError(f"`{binary}` is not installed or not available in PATH.") from exc
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or "").strip()
        if not message:
            pretty = " ".join(shlex.quote(part) for part in cmd)
            message = f"Command failed: {pretty}"
        raise RuntimeError(message) from exc


def sanitize_stem(name: str) -> str:
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1F]+', "_", name).strip()
    safe = re.sub(r"\s+", "_", safe)
    return safe[:120] or "file"


def to_size_label(size: int | None) -> str:
    if not size or size <= 0:
        return "size unknown"
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    idx = 0
    while value >= 1024 and idx < len(units) - 1:
        value /= 1024
        idx += 1
    decimals = 0 if idx == 0 else 1
    return f"{value:.{decimals}f} {units[idx]}"


def parse_video_formats(info: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    video_formats: list[dict[str, Any]] = []
    audio_formats: list[dict[str, Any]] = []

    for fmt in info.get("formats", []):
        format_id = str(fmt.get("format_id", "")).strip()
        if not format_id:
            continue

        vcodec = str(fmt.get("vcodec", "none"))
        acodec = str(fmt.get("acodec", "none"))
        is_video = vcodec != "none"
        is_audio = acodec != "none"
        ext = str(fmt.get("ext", "unknown"))
        filesize = fmt.get("filesize") or fmt.get("filesize_approx")
        fps = fmt.get("fps")
        height = fmt.get("height")
        abr = fmt.get("abr")

        if is_video:
            parts = []
            if height:
                parts.append(f"{height}p")
            elif fmt.get("resolution"):
                parts.append(str(fmt["resolution"]))
            parts.append(ext.upper())
            if fps:
                parts.append(f"{int(round(float(fps)))}fps")
            parts.append("with audio" if is_audio else "video only")
            parts.append(to_size_label(filesize))
            video_formats.append(
                {
                    "id": format_id,
                    "ext": ext,
                    "height": height or 0,
                    "fps": int(round(float(fps))) if fps else 0,
                    "filesize": filesize or 0,
                    "label": " | ".join(parts),
                }
            )

        if is_audio and not is_video:
            kbps = int(round(float(abr))) if abr else 0
            parts = [f"{kbps}kbps" if kbps else "audio", ext.upper(), to_size_label(filesize)]
            audio_formats.append(
                {
                    "id": format_id,
                    "ext": ext,
                    "abr": kbps,
                    "filesize": filesize or 0,
                    "label": " | ".join(parts),
                }
            )

    video_formats.sort(key=lambda item: (item["height"], item["fps"], item["filesize"]), reverse=True)
    audio_formats.sort(key=lambda item: (item["abr"], item["filesize"]), reverse=True)
    return video_formats, audio_formats


def find_downloaded_file(command_output: str) -> Path | None:
    patterns = [
        r"\[Merger\] Merging formats into \"(?P<path>.+?)\"",
        r"\[ExtractAudio\] Destination: (?P<path>.+)",
        r"\[download\] Destination: (?P<path>.+)",
        r"\[download\] (?P<path>.+?) has already been downloaded",
    ]

    for line in reversed(command_output.splitlines()):
        for pattern in patterns:
            match = re.search(pattern, line)
            if not match:
                continue
            candidate = Path(match.group("path").strip().strip('"'))
            if candidate.exists():
                return candidate

    files = [item for item in DOWNLOAD_DIR.iterdir() if item.is_file()]
    if not files:
        return None
    return max(files, key=lambda item: item.stat().st_mtime)


def convert_image_to_pdf(input_path: Path, output_path: Path) -> None:
    with Image.open(input_path) as image:
        rgb_image = image.convert("RGB")
        rgb_image.save(output_path, "PDF")


def convert_pdf_to_text(input_path: Path, output_path: Path) -> None:
    reader = PdfReader(str(input_path))
    pages_text = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(pages_text).strip()
    if not text:
        text = "No extractable text found in this PDF."
    output_path.write_text(text, encoding="utf-8")


def convert_with_ffmpeg(input_path: Path, output_path: Path) -> None:
    run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            str(output_path),
        ]
    )


def handle_conversion(input_path: Path, output_path: Path, source_ext: str, target_ext: str) -> None:
    if source_ext == target_ext:
        raise RuntimeError("Source and target formats are the same.")

    if source_ext in IMAGE_EXTENSIONS and target_ext == "pdf":
        convert_image_to_pdf(input_path, output_path)
        return

    if source_ext == "pdf" and target_ext == "txt":
        convert_pdf_to_text(input_path, output_path)
        return

    if source_ext in IMAGE_EXTENSIONS and target_ext in IMAGE_EXTENSIONS:
        with Image.open(input_path) as image:
            image.save(output_path)
        return

    if source_ext in MEDIA_EXTENSIONS and target_ext in MEDIA_EXTENSIONS:
        convert_with_ffmpeg(input_path, output_path)
        return

    raise RuntimeError(
        "Unsupported conversion. Try media-to-media, image-to-image, image-to-PDF, or PDF-to-TXT."
    )


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.get("/health")
def health() -> Any:
    return jsonify({"status": "ok"})


@app.post("/api/video/info")
def video_info() -> Any:
    payload = request.get_json(silent=True) or {}
    url = str(payload.get("url", "")).strip()
    if not url:
        return jsonify({"error": "URL is required."}), 400

    try:
        result = run_command(["yt-dlp", "--dump-single-json", "--no-playlist", url])
        info = json.loads(result.stdout)
        video_formats, audio_formats = parse_video_formats(info)
        return jsonify(
            {
                "title": info.get("title", "Untitled"),
                "uploader": info.get("uploader", "Unknown"),
                "duration": info.get("duration"),
                "thumbnail": info.get("thumbnail"),
                "video_formats": video_formats,
                "audio_formats": audio_formats,
            }
        )
    except json.JSONDecodeError:
        return jsonify({"error": "Could not parse video metadata."}), 500
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/video/download")
def video_download() -> Any:
    payload = request.get_json(silent=True) or {}
    url = str(payload.get("url", "")).strip()
    mode = str(payload.get("mode", "video")).strip().lower()
    format_id = str(payload.get("format_id", "")).strip()
    audio_format = str(payload.get("audio_format", "mp3")).strip().lower()

    if not url:
        return jsonify({"error": "URL is required."}), 400
    if mode not in {"video", "audio"}:
        return jsonify({"error": "Unsupported download mode."}), 400

    output_template = str(DOWNLOAD_DIR / "%(title).120s_%(id)s.%(ext)s")

    cmd = ["yt-dlp", "--no-playlist", "-o", output_template]
    if mode == "audio":
        if audio_format not in AUDIO_EXTENSIONS:
            return jsonify({"error": "Unsupported audio format."}), 400
        if format_id:
            cmd.extend(["-f", format_id])
        cmd.extend(["-x", "--audio-format", audio_format, url])
    else:
        if format_id:
            cmd.extend(["-f", format_id])
        else:
            cmd.extend(["-f", "bv*+ba/b"])
        cmd.extend(["--merge-output-format", "mp4", url])

    try:
        result = run_command(cmd)
        combined_output = f"{result.stdout}\n{result.stderr}".strip()
        downloaded_file = find_downloaded_file(combined_output)
        if downloaded_file is None:
            return jsonify({"error": "Download finished but file could not be located."}), 500
        return jsonify(
            {
                "filename": downloaded_file.name,
                "download_url": f"/files/downloads/{downloaded_file.name}",
            }
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/convert")
def convert_file() -> Any:
    upload = request.files.get("file")
    target_ext = str(request.form.get("target_format", "")).strip().lower()

    if not upload or not upload.filename:
        return jsonify({"error": "Please attach a file first."}), 400
    if not target_ext:
        return jsonify({"error": "Target format is required."}), 400
    if not re.fullmatch(r"[a-z0-9]{2,10}", target_ext):
        return jsonify({"error": "Invalid target format."}), 400

    source_path = Path(upload.filename)
    source_ext = source_path.suffix.lower().lstrip(".")
    if not source_ext:
        return jsonify({"error": "Input file has no extension."}), 400
    if not re.fullmatch(r"[a-z0-9]{2,10}", source_ext):
        return jsonify({"error": "Unsupported input extension."}), 400

    safe_stem = sanitize_stem(source_path.stem)
    unique_id = uuid.uuid4().hex
    upload_path = UPLOAD_DIR / f"{safe_stem}_{unique_id}.{source_ext}"
    output_path = CONVERTED_DIR / f"{safe_stem}_{unique_id}.{target_ext}"

    try:
        upload.save(upload_path)
        handle_conversion(upload_path, output_path, source_ext, target_ext)
        if not output_path.exists():
            return jsonify({"error": "Conversion did not produce an output file."}), 500
        return jsonify(
            {
                "filename": output_path.name,
                "download_url": f"/files/converted/{output_path.name}",
            }
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400


@app.get("/files/<bucket>/<path:filename>")
def file_download(bucket: str, filename: str) -> Any:
    roots = {
        "downloads": DOWNLOAD_DIR,
        "converted": CONVERTED_DIR,
    }
    root = roots.get(bucket)
    if root is None:
        abort(404)

    safe_name = Path(filename).name
    target = root / safe_name
    if not target.exists() or not target.is_file():
        abort(404)

    return send_from_directory(root, safe_name, as_attachment=True)


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )
