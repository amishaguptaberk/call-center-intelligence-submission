FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SPACE_ID=docker \
    DIARIZATION_BACKEND=heuristic \
    GRADIO_ANALYTICS_ENABLED=False \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home --uid 1000 appuser

COPY app.py .
COPY src ./src
COPY data/samples ./data/samples

RUN mkdir -p /app/.cache /app/var && chown -R appuser:appuser /app/data /app/.cache /app/var
USER appuser

EXPOSE 7860

CMD ["python", "app.py"]
