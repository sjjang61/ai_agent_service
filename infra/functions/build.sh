#!/bin/bash
# Function 런타임 이미지를 만든다: ./build.sh  (FUNCTION_RUNTIME_IMAGE_PYTHON / _BUN 기본 이름과 같다)
set -e
cd "$(dirname "$0")"
docker build -f Dockerfile.python -t ai-agent-fn-python:latest .
docker build -f Dockerfile.bun -t ai-agent-fn-bun:latest .
