FROM python:3.13-slim

ARG APP_VERSION=dev
# BREAK_HEALTH=1 builds a deliberately unhealthy release for the rollback drill.
ARG BREAK_HEALTH=0
ENV APP_VERSION=${APP_VERSION} BREAK_HEALTH=${BREAK_HEALTH} PYTHONUNBUFFERED=1

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data

RUN useradd --system --no-create-home appuser
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/healthz', timeout=2)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
