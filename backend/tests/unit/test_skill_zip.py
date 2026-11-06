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
