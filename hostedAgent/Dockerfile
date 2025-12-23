FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    procps \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://ollama.com/install.sh | sh

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml ./
COPY hostedAgent.py ./

RUN uv sync

EXPOSE 8088

ENV OLLAMA_BASE_URL=http://localhost:11434/v1/

RUN ollama serve & \
    sleep 5 && \
    ollama pull llama3.2:3b && \
    pkill ollama

# Create startup script that runs Ollama and the agent
RUN echo '#!/bin/bash\n\
ollama serve &\n\
echo "Waiting for Ollama to start..."\n\
sleep 5\n\
echo "Starting agent server..."\n\
uv run hostedAgent.py\n\
' > /app/start.sh && chmod +x /app/start.sh

CMD ["/app/start.sh"]
