   FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
   WORKDIR /app

   COPY pyproject.toml uv.lock ./
   RUN uv sync --frozen --no-install-project --no-dev

   COPY . .
   RUN uv sync --frozen --no-dev

   EXPOSE 8000
   CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
