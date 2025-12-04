# Multi-stage build for filesystem-mcp-server
FROM python:3.12-slim AS builder

WORKDIR /build

RUN pip install --no-cache-dir uv

COPY pyproject.toml .python-version ./
COPY src ./src

RUN uv venv && \
    uv pip install --no-cache .

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /build/.venv /app/.venv
COPY --from=builder /build/src /app/src
COPY --from=builder /build/pyproject.toml /app/pyproject.toml

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8123

VOLUME ["/data"]

ENTRYPOINT ["python", "-m", "filesystem.server"]
CMD ["--allowed-root", "/data", "--port", "8123"]
