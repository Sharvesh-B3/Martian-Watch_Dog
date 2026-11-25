FROM python:3.13.7-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY sim/requirements.txt /tmp/requirements.txt
RUN python -m pip install --requirement /tmp/requirements.txt

COPY sim/__init__.py /app/sim/__init__.py
COPY sim/common /app/sim/common
COPY sim/devices /app/sim/devices
COPY sim/attacks /app/sim/attacks
COPY sim/contracts/*.schema.json /app/sim/contracts/

RUN addgroup --system watchdog \
    && adduser --system --ingroup watchdog --home /nonexistent --no-create-home watchdog \
    && chown -R watchdog:watchdog /app

USER watchdog

CMD ["python", "-m", "sim.devices.smart_lock"]
