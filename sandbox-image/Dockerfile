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

# Node.js (npx/npm): k-skill 같은 스킬이 `npx ...`, `npm install -g ...` 로 지침과 패키지를 받아온다
COPY --from=node:22-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:22-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && mkdir -p /home/sandbox-npm && chmod 777 /home/sandbox-npm
# non-root 유저가 `npm install -g` 할 수 있도록 전역 설치 위치를 쓰기 가능한 경로로 둔다
ENV NPM_CONFIG_PREFIX=/home/sandbox-npm/global
ENV PATH=/home/sandbox-npm/global/bin:$PATH

# Workspace directory
WORKDIR /workspace
RUN chmod 777 /workspace

# Security: non-root user
RUN useradd -m -u 1000 sandbox
USER sandbox

ENTRYPOINT ["tail", "-f", "/dev/null"]
