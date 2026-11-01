FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY backend/app ./backend/app
COPY ai-pipeline/serving.py ./ai-pipeline/serving.py
COPY ai-pipeline/artifacts ./ai-pipeline/artifacts
RUN useradd --create-home --uid 10001 app && mkdir -p backend/runtime && chown -R app:app /workspace
USER app
WORKDIR /workspace/backend
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
