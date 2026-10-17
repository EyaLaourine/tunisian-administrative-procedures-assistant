FROM python:3.11-slim
WORKDIR /app
COPY telegram_bridge/requirements.txt /app/telegram-requirements.txt
RUN pip install --no-cache-dir -r /app/telegram-requirements.txt
# Share only environment parsing and safe logging, without importing backend agents or retrieval.
COPY backend/__init__.py backend/settings.py backend/logging_setup.py /app/backend/
COPY telegram_bridge/*.py /app/telegram_bridge/
RUN useradd --create-home --uid 10001 appuser
USER appuser
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["python", "-m", "telegram_bridge", "--wait-for-token"]
