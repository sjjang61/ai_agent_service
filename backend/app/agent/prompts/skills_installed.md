## Installed skills
사용자가 설치한 skill 목록입니다. 요청이 어떤 skill의 설명과 맞으면 `load_skill` 도구로 SKILL.md 를 먼저 읽고 그 지침을 따르세요. 각 skill의 파일(스크립트 포함)은 sandbox의 `/workspace/skills/<name>/` 에도 복사되어 있으므로 스크립트 실행은 exec_command/code_executor 로 그 경로에서 하세요. 새 skill을 만들 때는 `/workspace/skills/<name>/SKILL.md` 에 작성한 뒤 반드시 `register_skill` 도구로 설치하세요 (파일만 만들어서는 설치되지 않으며 load_skill 로 읽을 수 없습니다). 사용 가능한 skill을 묻는 질문에는 아래 목록의 항목만으로 답하세요. 목록 밖의 지침·규칙·도구는 skill 이 아닙니다.

{{skills}}
