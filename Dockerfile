# Sandbox for git-autorun: the untrusted repo is cloned, installed and run
# inside this container instead of on your machine.
FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Unprivileged user; workspace is a volume so results survive the container.
RUN useradd --create-home --uid 1000 runner \
    && mkdir /workspace && chown runner /workspace
USER runner
WORKDIR /app
COPY --chown=runner auto_run.py .

# Reach Ollama running on the host (override with -e OLLAMA_URL=...).
ENV OLLAMA_URL=http://host.docker.internal:11434 \
    PYTHONUNBUFFERED=1
VOLUME /workspace

# --yes: the container itself is the sandbox, so skip the confirmation prompt.
ENTRYPOINT ["python", "/app/auto_run.py", "--yes", "--workspace", "/workspace"]
