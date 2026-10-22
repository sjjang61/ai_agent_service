import io
import json
import zipfile

import pytest
from fastapi import HTTPException

from app.services.skill_service import GithubRef, _extract_skills, _find_plugins


def _zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, body in files.items():
            zf.writestr(f"o-r-abc/{name}", body)
    return buf.getvalue()


def _skill(name: str) -> str:
    return f"---\nname: {name}\ndescription: {name} desc\n---\nbody"


G = GithubRef("o", "r", None, "")


def test_single_plugin_with_skills(tmp_path):
    data = _zip({
        ".claude-plugin/plugin.json": json.dumps({"name": "My Plugin", "version": "1.2.0", "description": "d"}),
        "skills/a/SKILL.md": _skill("a"),
        "skills/b/SKILL.md": _skill("b"),
    })
    plugins = _find_plugins(data, G)
    assert [(p["name"], p["version"]) for p in plugins] == [("my-plugin", "1.2.0")]
    skills = _extract_skills(data, G, tmp_path, plugins[0]["root"])
    assert sorted(s["name"] for s in skills) == ["a", "b"]


def test_marketplace_local_sources_only(tmp_path):
    data = _zip({
        ".claude-plugin/marketplace.json": json.dumps({"plugins": [
            {"name": "p1", "source": "./plugins/p1"},
            {"name": "ext", "source": {"source": "github", "repo": "x/y"}},
        ]}),
        "plugins/p1/skills/s1/SKILL.md": _skill("s1"),
    })
    plugins = _find_plugins(data, G)
    assert [p["name"] for p in plugins] == ["p1"]
    skills = _extract_skills(data, G, tmp_path, plugins[0]["root"])
    assert [s["name"] for s in skills] == ["s1"]


def test_not_a_plugin():
    with pytest.raises(HTTPException) as e:
        _find_plugins(_zip({"skills/a/SKILL.md": _skill("a")}), G)
    assert e.value.status_code == 404


def test_marketplace_path_traversal_ignored():
    data = _zip({".claude-plugin/marketplace.json": json.dumps({"plugins": [{"name": "x", "source": "./../evil"}]})})
    with pytest.raises(HTTPException):
        _find_plugins(data, G)


def test_frontmatter_block_scalar_description():
    from app.services.skill_service import _parse_frontmatter

    meta = _parse_frontmatter("---\nname: x\ndescription: >\n  first line\n  second line\nlicense: MIT\n---\nbody")
    assert meta == {"name": "x", "description": "first line second line", "license": "MIT"}
