FROM python:3.13.7-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.txt /tmp/requirements.txt
RUN python -m pip install -r /tmp/requirements.txt
COPY backend /app/backend
COPY sim/contracts/*.schema.json /app/sim/contracts/
RUN addgroup --system watchdog && adduser --system --ingroup watchdog --no-create-home watchdog \
    && mkdir -p /data && chown -R watchdog:watchdog /app /data
USER watchdog
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
