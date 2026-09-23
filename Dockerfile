FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev

FROM python:3.14-slim-bookworm

RUN useradd --create-home --uid 10001 kese
WORKDIR /app
COPY --from=builder --chown=kese:kese /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER kese
EXPOSE 8000
CMD ["uvicorn", "kese.main:app", "--host", "0.0.0.0", "--port", "8000"]
