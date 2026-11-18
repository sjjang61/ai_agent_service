#!/bin/bash
# Function 런타임 진입점. 읽기 전용 루트 파일시스템이라 컨테이너에 파일을 미리 넣을 수 없어서, 백엔드가 stdin 으로 보내 준다:
#   PKG <바이트수>\n<tar 바이트...>   : 검증·정규화된 패키지 → /var/task (tmpfs) 에 푼다
#   EVT <바이트수>\n<json 바이트...>  : 이벤트 → /tmp/event.json
# 이어서 인자로 받은 런타임 명령(python bootstrap.py 등)을 실행한다.
set -e
read -r tag n
[ "$tag" = "PKG" ] || { echo "bad protocol" >&2; exit 70; }
head -c "$n" | tar -x --no-same-owner -C /var/task
read -r tag m
[ "$tag" = "EVT" ] || { echo "bad protocol" >&2; exit 70; }
head -c "$m" > /tmp/event.json
cd /var/task
exec "$@"
