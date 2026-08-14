FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
RUN timeout 300 python -m pip install --upgrade pip \
    && timeout 300 python -m pip install --retries 10 --timeout 100 --no-cache-dir ".[dev]"

RUN mkdir -p /workspace
WORKDIR /workspace
EXPOSE 8000
CMD ["harness", "demo", "--workspace", "/workspace"]
