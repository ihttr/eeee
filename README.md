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
2. `yt-dlp` installed and available in PATH.
3. `ffmpeg` installed and available in PATH.

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

## Output files

Generated files are stored under:

- `workspace/downloads`
- `workspace/converted`
- `workspace/uploads` (temporary uploads)

## Note

Use this app only for content you own or are authorized to download.
