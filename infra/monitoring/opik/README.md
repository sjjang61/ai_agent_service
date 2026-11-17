# Opik 자체 호스팅 (에이전트 응답 모니터링)

백엔드(`AGENT_MONITORING_TYPE=opik`)가 OpenTelemetry 로 트레이스를 보내는 대상이다. Opik 공식 compose(v2.2.143, Apache-2.0)를 가져와 포트만 정리했다.

```bash
cd infra/monitoring/opik
docker compose --profile opik up -d      # 첫 실행은 이미지 내려받기 + DB 마이그레이션으로 수 분 걸린다
docker compose --profile opik ps         # backend 가 healthy 가 되면 준비 완료
open http://localhost:15174              # 화면 (API 도 같은 포트: /api/v1/private/…)
docker compose --profile opik down       # 중지 (데이터 볼륨은 유지). 데이터까지 지우려면 down -v
```

- 호스트에 여는 포트는 `NGINX_PORT`(15174) 하나뿐이다. 개발 PC 의 MySQL(3306)·Redis(6379)·Vite(5173) 등과 겹치지 않도록 인프라 포트는 열지 않았다.
- `COMPOSE_PROJECT_NAME=ai-agent-opik`: 이 PC 에 이미 있을 수 있는 다른 Opik 볼륨(`opik_*`)과 섞이지 않게 고유한 이름을 쓴다. 옛 Opik 의 잠긴 DB 와 충돌하는 문제를 겪었다.
- 이미지 버전은 `.env` 의 `OPIK_VERSION` 으로 고정한다 (저장소 최신 태그가 아니라 **릴리스된 태그**를 써야 한다).
- 프롬프트·도구 결과 전문이 저장된다. 접근은 내부망으로 제한하고, 운영에서는 인증·보존 기간을 정한다.

확인 스크립트: `backend/scripts/monitoring_poc.py`(시나리오 실행), `backend/scripts/monitoring_check.py`(서버에서 트리 확인).
