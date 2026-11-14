# Backend + pipeline image. Build context is the repository root:
#   docker build -f backend/Dockerfile --build-arg GIT_SHA=$(git rev-parse HEAD) .
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON_PREFERENCE=only-system \
    UV_PYTHON=/usr/local/bin/python3.12 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first (cached layer), then the project itself.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --extra storage --no-install-project

COPY core ./core
COPY backend ./backend
COPY pipeline ./pipeline
COPY config ./config
COPY alembic.ini ./
RUN uv sync --frozen --no-dev --extra storage

ARG GIT_SHA=unknown
ENV GIT_SHA=${GIT_SHA} \
    PATH=/opt/venv/bin:${PATH} \
    EAE_DATA_DIR=/data \
    EAE_CONFIG_DIR=/app/config

RUN useradd --create-home --uid 1000 eae && mkdir -p /data && chown eae /data
USER eae

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
