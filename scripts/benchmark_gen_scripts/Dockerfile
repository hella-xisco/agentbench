# syntax=docker/dockerfile:1
# Container for running google/adk-python on x86 (linux/amd64).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PIP_NO_CACHE_DIR=1

# System deps for building wheels and tools used by tests (git, graphviz).
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    graphviz \
    curl \
    pkg-config \
    libffi-dev \
    libssl-dev \
  && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Allow pinning a specific ref/branch/tag at build time.
ARG REF=main

# Use /testbed to match Planbench expectations.
WORKDIR /testbed
RUN git clone --branch "${REF}" <REPO_URL> .

CMD ["/bin/bash"]

# DOCKER_BUILDKIT=1 DOCKER_DEFAULT_PLATFORM=linux/amd64 docker build -t tgloaguen/planbenchx86_opshin_opshin:latest .
# docker run --rm -it --platform=linux/amd64 -w /testbed tgloaguen/planbenchx86_opshin_opshin:latest /bin/bash
