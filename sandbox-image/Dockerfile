FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    curl wget git bash vim fonts-noto-cjk \
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
# 브라우저를 /root 가 아닌 공용 경로에 설치해야 아래 non-root(sandbox) 유저가 실행할 수 있다
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install chromium --with-deps && chmod -R a+rX /ms-playwright

# Workspace directory
WORKDIR /workspace
RUN chmod 777 /workspace

# Security: non-root user
RUN useradd -m -u 1000 sandbox
USER sandbox

ENTRYPOINT ["tail", "-f", "/dev/null"]
