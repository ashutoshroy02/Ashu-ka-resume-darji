FROM python:3.11-slim

# LaTeX engine (tectonic — self-contained, no full texlive needed) +
# Playwright's Chromium system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl xz-utils ca-certificates \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# tectonic — resolve the current version from the (unthrottled) releases
# redirect rather than hardcoding a version number or hitting the
# rate-limited api.github.com REST API (60 req/hr/IP — shared build infra
# hits this easily and it fails the whole build with no fallback).
RUN TECTONIC_TAG="$(curl -sI https://github.com/tectonic-typesetting/tectonic/releases/latest \
        | grep -i '^location:' | sed -E 's#.*/tag/tectonic@##' | tr -d '\r\n')" \
    && echo "Resolved tectonic version: $TECTONIC_TAG" \
    && wget -qO- "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic@${TECTONIC_TAG}/tectonic-${TECTONIC_TAG}-x86_64-unknown-linux-gnu.tar.gz" \
        | tar xz -C /usr/local/bin

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium --with-deps

COPY . .

# Shell form so $PORT (set by Render at runtime) actually expands —
# the array/exec form of CMD does NOT do env var substitution.
CMD uvicorn main:app --host 0.0.0.0 --port $PORT