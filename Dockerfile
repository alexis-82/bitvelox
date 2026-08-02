FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV PATH="/venv/bin:$PATH"
ENV MUSIC_DIR=/music DATA_DIR=/data HTTP_PORT=4040

RUN groupadd -r app -g 1000 && useradd -r -u 1000 -g app -m -d /home/app app

COPY --from=builder /venv /venv
COPY --from=builder /build/src /app/src
COPY CHANGELOG.md /app/CHANGELOG.md

RUN mkdir -p /music /data && chown -R app:app /music /data /app

USER app
WORKDIR /app

EXPOSE 4040

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${HTTP_PORT}"]
