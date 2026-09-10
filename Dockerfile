FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.14-slim-bookworm
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    HOST=0.0.0.0 \
    PORT=8787 \
    PATH="/app/.venv/bin:/usr/local/bin:$PATH"

RUN python -m pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv --version && uv sync --frozen --no-dev
COPY --from=web /web/dist ./web/dist

RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

EXPOSE 8787
CMD ["sh", "-c", "exec freight-sb ui --host 0.0.0.0 --port ${PORT:-8787}"]
