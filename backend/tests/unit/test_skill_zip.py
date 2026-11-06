import io
import zipfile

import pytest
from fastapi import HTTPException

from app.services.skill_service import GithubRef, _extract_skills, _normalize_upload_zip

MD = "---\nname: my-skill\ndescription: 테스트 스킬\n---\n\n본문\n"


def _zip(files: dict) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for k, v in files.items():
            z.writestr(k, v)
    return b.getvalue()


def _install(files: dict, tmp_path, stem="upload-test"):
    norm = _normalize_upload_zip(_zip(files), stem)
    return _extract_skills(norm, GithubRef("", stem, None, ""), tmp_path)


def test_root_level_skill_md(tmp_path):
    r = _install({"SKILL.md": MD, "scripts/run.py": "print(1)"}, tmp_path)
    assert [x["name"] for x in r] == ["my-skill"]
    assert (tmp_path / "my-skill" / "scripts" / "run.py").is_file()


def test_single_folder(tmp_path):
    r = _install({"foo/SKILL.md": MD, "foo/ref.md": "x"}, tmp_path)
    assert r[0]["description"] == "테스트 스킬" and (tmp_path / "my-skill" / "ref.md").is_file()


def test_multiple_folders_and_junk(tmp_path):
    r = _install({
        "a/SKILL.md": MD.replace("my-skill", "a-skill"),
        "b/SKILL.md": MD.replace("my-skill", "b-skill"),
        "__MACOSX/a/._SKILL.md": "junk",
        "a/.DS_Store": "junk",
    }, tmp_path)
    assert sorted(x["name"] for x in r) == ["a-skill", "b-skill"]
    assert not (tmp_path / "a-skill" / ".DS_Store").exists()


def test_no_skill_md(tmp_path):
    with pytest.raises(HTTPException) as e:
        _install({"foo/readme.md": "x"}, tmp_path)
    assert e.value.status_code == 404


def test_bad_zip_and_path_escape(tmp_path):
    with pytest.raises(HTTPException) as e:
        _normalize_upload_zip(b"not a zip", "x")
    assert e.value.status_code == 400
    r = _install({"../evil/SKILL.md": MD, "ok/SKILL.md": MD.replace("my-skill", "ok-skill")}, tmp_path)
    assert [x["name"] for x in r] == ["ok-skill"]
    assert not (tmp_path.parent / "evil").exists()


PJ = '{"name": "my-plugin", "description": "테스트 플러그인", "version": "1.2.0"}'


def _plugin(files: dict, tmp_path, stem="plug"):
    from app.services.skill_service import _find_plugins

    norm = _normalize_upload_zip(_zip(files), stem)
    g = GithubRef("", stem, None, "")
    found = _find_plugins(norm, g)
    return found, [_extract_skills(norm, g, tmp_path, pl["root"]) for pl in found]


def test_plugin_zip_root_level(tmp_path):
    found, skills = _plugin({
        ".claude-plugin/plugin.json": PJ,
        "skills/a/SKILL.md": MD.replace("my-skill", "a-skill"),
        "skills/b/SKILL.md": MD.replace("my-skill", "b-skill"),
    }, tmp_path)
    assert [(f["name"], f["version"]) for f in found] == [("my-plugin", "1.2.0")]
    assert sorted(x["name"] for x in skills[0]) == ["a-skill", "b-skill"]


def test_plugin_zip_inside_folder(tmp_path):
    found, skills = _plugin({"myplug/.claude-plugin/plugin.json": PJ, "myplug/skills/a/SKILL.md": MD}, tmp_path)
    assert found[0]["name"] == "my-plugin" and skills[0][0]["name"] == "my-skill"


def test_not_a_plugin():
    from app.services.skill_service import _find_plugins

    with pytest.raises(HTTPException) as e:
        _find_plugins(_normalize_upload_zip(_zip({"x/SKILL.md": MD}), "x"), GithubRef("", "x", None, ""))
    assert e.value.status_code == 404


def test_skill_file_listing_and_read(tmp_path):
    from types import SimpleNamespace

    from app.services.skill_service import SkillService

    (tmp_path / "scripts").mkdir()
    (tmp_path / "SKILL.md").write_text(MD, encoding="utf-8")
    (tmp_path / "scripts" / "a.py").write_text("print(1)")
    (tmp_path / "logo.bin").write_bytes(b"\x00\x01")
    (tmp_path / "link").symlink_to(tmp_path / "SKILL.md")
    sk = SimpleNamespace(install_path=str(tmp_path))
    files, trunc = SkillService.list_files(sk)
    assert files[0]["path"] == "SKILL.md" and {f["path"] for f in files} == {"SKILL.md", "scripts/a.py", "logo.bin"}
    assert SkillService.read_file(sk, "SKILL.md")["content"].startswith("---")
    assert SkillService.read_file(sk, "logo.bin")["binary"] is True
    for bad in ("../x", "link", "missing.txt", "/etc/passwd"):
        with pytest.raises(HTTPException):
            SkillService.read_file(sk, bad)


def test_skills_prompt_marks_custom_and_sync_skips_custom():
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import patch

    from app.services.skill_service import SkillService
    from app.tools.skill_tool import build_skills_prompt

    skills = [
        SimpleNamespace(name="a", description="빌트인", skill_type="builtin", install_path="/x"),
        SimpleNamespace(name="b", description="커스텀", skill_type="custom", install_path="/y"),
    ]
    p = build_skills_prompt(skills)
    assert "- a: 빌트인" in p and "- b [custom]: 커스텀" in p and "custom" in p.split("{{")[0]

    async def go():
        copied = []

        async def fake_list(user_id, db):
            return [(SimpleNamespace(status="running", container_id="c1"), None)]

        class M:
            async def is_running(self, cid): return True
            async def put_directory(self, cid, path, dest, name): copied.append(name)

        with patch("app.services.skill_service.SandboxService.list_for_user", fake_list), patch("app.services.skill_service.sandbox_manager", M()):
            assert await SkillService.sync_to_sandbox("u", skills, None) is None
        return copied

    assert asyncio.run(go()) == ["a"]               # custom 은 자동 설치하지 않는다
