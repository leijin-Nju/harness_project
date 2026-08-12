FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
RUN pip install --no-cache-dir .[dev]

RUN mkdir -p /workspace
WORKDIR /workspace
EXPOSE 8000
CMD ["harness", "demo", "--workspace", "/workspace"]
