# Sandbox 격리

## 구조

| 종류 | 대상 | 컨테이너 | MinIO 백업 키 |
|---|---|---|---|
| 대화방 전용 | 일반 채팅 대화방마다 1개 | 대화방마다 독립 (workspace·패키지·프로세스 분리) | `{conversation_id}/workspace.tar.gz` |
| 사용자 공용 | 스페이스에서 시작한 대화(`conversations.space_id`), 대화방별 sandbox 도입 전의 기존 sandbox | 사용자당 1개 | `{Sandbox.id}/workspace.tar.gz` (기존과 동일) |

- `sandboxes.conversation_id` 가 NULL 이면 공용, 값이 있으면 그 대화방 전용이다.
- 어떤 sandbox 를 쓸지는 `resolve_scope(conversation_id)` 가 정한다 (`space_id` 가 있는 대화는 공용). 오케스트레이터가 요청마다 한 번 정해 모든 sandbox 도구(`sandbox_cid`)와 복구에 넘긴다. API(`/sandbox/*`)는 `conversation_id` 를 받고, 없으면 공용이다.
- 대화방 sandbox 는 도구를 처음 쓸 때 만들어진다 (생성 약 1초). 5분 동안 쓰지 않으면 백업 후 종료하고, 그 대화방에서 요청이 시작되면 백업이 있을 때 복구한다.
- 대화방을 삭제하면 그 sandbox 의 컨테이너·MinIO 백업·행도 함께 지운다. 공용 sandbox 는 사용자가 샌드박스 화면에서 직접 삭제한다.
- 사용자당 동시 실행 상한 `SANDBOX_MAX_RUNNING_PER_USER`(기본 5)를 넘기면 가장 오래 쓰지 않은 sandbox 를 백업 후 종료한다.
- 활성 스킬은 컨테이너를 만들 때 복사한다. 스킬을 설치·삭제하면 실행 중인 모든 sandbox 에 반영한다.

## 네트워크

- sandbox 컨테이너는 전용 네트워크 `SANDBOX_NETWORK`(기본 `sandbox-network`)에 붙고, 이 네트워크는 **컨테이너 간 통신(icc)을 막아** 둔다. 다른 사용자·다른 대화방의 sandbox 에 접근할 수 없다. 외부 인터넷은 허용한다.
- 만들 수 없으면 기본 bridge 로 폴백하고 경고를 남긴다 (이 경우 컨테이너 간 통신이 열려 있으니 로그를 확인한다).
- 업그레이드 전에 만들어진 컨테이너는 기본 bridge 에 남아 있다. 유휴 종료 후 다시 만들어질 때 전용 네트워크로 옮겨진다.

## 아직 남은 위험: 호스트 서비스 접근

Docker Desktop 처럼 컨테이너에서 호스트로 가는 경로(`host.docker.internal`)가 열려 있으면, sandbox 안의 코드가 호스트에 공개된 포트(MySQL 3306, Redis 6379, 백엔드 8500, MinIO 9000)에 접속할 수 있다. 컨테이너 간 차단(icc)으로는 막을 수 없다. 운영 환경에서는 아래 중 하나를 적용한다.

- DB·Redis·MinIO 를 호스트에 공개하지 말고 내부 네트워크에만 둔다 (포트 게시 제거).
- Linux 서버: `DOCKER-USER` 체인에서 sandbox 네트워크 대역 → 호스트/내부 서비스 대역을 DROP.
- Kubernetes: sandbox 파드에 NetworkPolicy (egress 는 인터넷만 허용, 클러스터 내부 대역 차단).
- 가능하면 sandbox 컨테이너를 별도 호스트(또는 VM)에서 돌린다.
