FROM mcr.microsoft.com/devcontainers/go:1-1.26-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends just pre-commit postgresql-client curl \
    && rm -rf /var/lib/apt/lists/*
