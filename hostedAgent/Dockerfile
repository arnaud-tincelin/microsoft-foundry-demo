FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    procps \
    zstd \
    && rm -rf /var/lib/apt/lists/*

# Hosted compute is CPU-only; exclude GPU libraries from the installation layer.
RUN curl -fsSL https://ollama.com/install.sh | sh \
    && rm -rf /usr/local/lib/ollama/cuda_v12 \
        /usr/local/lib/ollama/cuda_v13 \
        /usr/local/lib/ollama/vulkan

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
COPY hostedAgent.py ./

RUN uv sync --frozen --no-cache

EXPOSE 8088

ENV OLLAMA_BASE_URL=http://localhost:11434/v1/
# Foundry replaces HOME for each session; baked model weights must live outside it.
ENV OLLAMA_MODELS=/opt/ollama/models

RUN set -eu; \
    ollama serve & \
    ollama_pid=$!; \
    trap 'kill "$ollama_pid"' EXIT; \
    sleep 5; \
    ollama pull llama3.2:3b

# Create startup script that runs Ollama and the agent
RUN echo '#!/bin/bash\n\
ollama serve &\n\
echo "Waiting for Ollama to start..."\n\
sleep 5\n\
echo "Starting agent server..."\n\
uv run --frozen hostedAgent.py\n\
' > /app/start.sh && chmod +x /app/start.sh

CMD ["/app/start.sh"]
