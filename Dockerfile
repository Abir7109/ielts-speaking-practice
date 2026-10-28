FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/

ENV PORT=8000
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD exec python -m uvicorn backend.server:app_socketio --host 0.0.0.0 --port ${PORT} --ws-ping-interval 25 --ws-ping-timeout 20
