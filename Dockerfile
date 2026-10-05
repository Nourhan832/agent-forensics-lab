FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AFL_DATABASE_PATH=/data/agent_forensics.db
COPY requirements-lock.txt ./
RUN pip install --no-cache-dir -r requirements-lock.txt && useradd --uid 10001 --create-home appuser && mkdir /data && chown appuser /data
COPY backend ./backend
COPY frontend ./frontend
COPY data/emergency_response/usgs_events_v1.json ./data/emergency_response/usgs_events_v1.json
COPY experiments/corpora/emergency_response_v2.json ./experiments/corpora/emergency_response_v2.json
USER appuser
EXPOSE 8000
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/health', timeout=3)"
CMD ["python", "-m", "backend.app.api.serve"]
