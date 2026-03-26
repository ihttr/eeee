FROM python:3.11-slim

# تثبيت ffmpeg
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

ENV PORT=10000

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]
