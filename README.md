# Media Forge (Web App)

Modern dark web app for:

- downloading video/audio with quality selection,
- converting files from one format to another (including image-to-PDF and PDF-to-TXT),
- getting direct download links for generated outputs.

## Features

- Stream analysis with `yt-dlp` (video and audio formats).
- Video download by selected quality.
- Audio download with output format selection (`mp3`, `wav`, `m4a`, etc.).
- File conversion:
  - media-to-media via `ffmpeg`,
  - image-to-image via Pillow,
  - image-to-PDF,
  - PDF-to-TXT extraction.
- Responsive modern dark interface for desktop and mobile.

## Requirements

1. Python 3.10+.
2. `ffmpeg` installed and available in PATH.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Then open:

`http://127.0.0.1:5000`

## Deploy Online

You can deploy this app quickly with Docker-based hosting.

### Option 1: Render (fastest from this repo)

1. Push this project to GitHub.
2. In Render, create a new **Blueprint** service from the repo.
3. Render will detect `render.yaml` and deploy with `Dockerfile`.
4. Open your Render URL after deploy finishes.

### Option 2: Railway/Fly.io/any Docker host

1. Push this project to GitHub.
2. Create a new Docker-based service.
3. Point it to this repo (it will use `Dockerfile`).
4. Set env var `MEDIA_FORGE_STORAGE_DIR=/tmp/media-forge`.

### Important cloud note

Most cloud file systems are temporary. Downloaded/converted files may be deleted on restart unless you attach persistent storage.

## Output files

Generated files are stored under:

- `workspace/downloads`
- `workspace/converted`
- `workspace/uploads` (temporary uploads)

## Note

Use this app only for content you own or are authorized to download.
