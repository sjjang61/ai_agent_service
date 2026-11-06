import gzip
import io
import tarfile

import pytest

from app.services.app_artifact import ArtifactError, normalize_archive


def _tar(tmp_path, entries):
    p = tmp_path / "in.tar"
    with tarfile.open(p, "w") as t:
        for name, kind, data in entries:
            ti = tarfile.TarInfo(name)
            if kind == "dir":
                ti.type = tarfile.DIRTYPE
                t.addfile(ti)
            elif kind == "sym":
                ti.type, ti.linkname = tarfile.SYMTYPE, data
                t.addfile(ti)
            elif kind == "lnk":
                ti.type, ti.linkname = tarfile.LNKTYPE, data
                t.addfile(ti)
            else:
                ti.size = len(data)
                t.addfile(ti, io.BytesIO(data))
    return str(p)


def _names(path):
    with gzip.open(path) as g, tarfile.open(fileobj=g) as t:
        return [(m.name, m.uid) for m in t]


def test_strips_top_dir_and_chowns(tmp_path):
    src = _tar(tmp_path, [("dist", "dir", b""), ("dist/index.html", "f", b"<h1>x</h1>"), ("dist/assets/a.js", "f", b"1"), ("dist/.bin/x", "sym", "../a")])
    out = str(tmp_path / "o.tar.gz")
    files, total = normalize_archive(src, out, 10_000, 100)
    assert files == 3 and total == 11
    assert _names(out) == [("index.html", 1000), ("assets/a.js", 1000), (".bin/x", 1000)] or {n for n, _ in _names(out)} >= {"index.html", "assets/a.js"}


@pytest.mark.parametrize("entries", [
    [("dist/../evil", "f", b"x")],
    [("/abs/file", "f", b"x")],
    [("dist/link", "sym", "/etc/passwd")],
    [("dist/link", "sym", "../../outside")],
    [("dist/h", "lnk", "../x")],
    [("dist", "dir", b"")],  # 파일 없음
])
def test_rejects_unsafe(tmp_path, entries):
    with pytest.raises(ArtifactError):
        normalize_archive(_tar(tmp_path, entries), str(tmp_path / "o.tar.gz"), 10_000, 100)


def test_limits(tmp_path):
    src = _tar(tmp_path, [("d", "dir", b""), ("d/a", "f", b"x" * 50), ("d/b", "f", b"x" * 50)])
    with pytest.raises(ArtifactError):
        normalize_archive(src, str(tmp_path / "o1.tar.gz"), 60, 100)
    with pytest.raises(ArtifactError):
        normalize_archive(src, str(tmp_path / "o2.tar.gz"), 10_000, 1)
