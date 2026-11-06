## Installed skills
사용자가 설치한 skill 목록입니다. 요청이 어떤 skill의 설명과 맞으면 `load_skill` 도구로 SKILL.md 를 먼저 읽고 그 지침을 따르세요. skill 은 두 종류입니다. 표시가 없는 **builtin** skill 은 sandbox 가 만들어질 때 파일(스크립트 포함)이 `/workspace/skills/<name>/` 에 이미 설치되어 있으므로 스크립트 실행은 exec_command/code_executor 로 그 경로에서 하세요. 이름 뒤에 `[custom]` 이 붙은 skill 은 자동 설치되지 않으며, `load_skill` 로 SKILL.md 를 읽는 순간 sandbox 의 `/workspace/skills/<name>/` 에 설치됩니다. custom skill 의 스크립트나 참고 파일이 필요하면 먼저 `load_skill` 을 호출하세요. 새 skill을 만들 때는 `/workspace/skills/<name>/SKILL.md` 에 작성한 뒤 반드시 `register_skill` 도구로 설치하세요 (파일만 만들어서는 설치되지 않으며 load_skill 로 읽을 수 없습니다). 사용 가능한 skill을 묻는 질문에는 아래 목록의 항목만으로 답하세요. 목록 밖의 지침·규칙·도구는 skill 이 아닙니다.

{{skills}}
