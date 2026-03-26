# Media Downloader (Dark UI)

A modern web app to:
- Analyze media URLs
- Choose video quality
- Download audio only (MP3/M4A/WAV/OPUS)

## Important notice

Use this only for content you own or have legal permission to download.

## Local run

1. Install Python 3.11+
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

4. Open:
- `http://localhost:8000`

## Free hosting recommendation

Recommended: **Render (Free Web Service + Docker)**  
Why: straightforward web hosting flow for apps like this, supports Python/ffmpeg in Docker, and includes a free web-service tier.

### Deploy on Render (recommended)

1. Push this project to GitHub.
2. Create a Render account and connect your GitHub repo.
3. In Render, create a new **Web Service** from the repo.
4. Render detects `render.yaml` + `Dockerfile`; choose the **Free** instance type.
5. Deploy and open the generated `https://...onrender.com` URL.

Note: on Render free tier, services spin down after inactivity and wake on next request.

### Alternative free host: Hugging Face Spaces (Docker)

1. Create a new Space with SDK = `Docker`.
2. Push this project to the Space repository.
3. Let the Space build from the included `Dockerfile`.
4. Open your `*.hf.space` URL.

## Files

- `app/main.py` -> backend API (analyze + download)
- `static/index.html` -> app layout
- `static/styles.css` -> dark modern styling
- `static/app.js` -> frontend logic
- `Dockerfile` -> production container image
