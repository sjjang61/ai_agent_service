FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    curl wget git bash vim \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Install common Python packages
RUN pip install \
    requests \
    httpx \
    pandas \
    numpy \
    matplotlib \
    playwright \
    beautifulsoup4

# Install Playwright browsers
RUN playwright install chromium --with-deps

# Workspace directory
WORKDIR /workspace
RUN chmod 777 /workspace

# Security: non-root user
RUN useradd -m -u 1000 sandbox
USER sandbox

ENTRYPOINT ["tail", "-f", "/dev/null"]
