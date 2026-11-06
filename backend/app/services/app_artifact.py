"""웹앱 배포 아카이브: 컨테이너에서 꺼낸 tar 를 검증·정규화(최상위 디렉터리 제거, 소유자 1000)해 tar.gz 로 저장한다. 앱 전용 정적 서버 스크립트도 여기 있다."""
import gzip
import posixpath
import tarfile
from pathlib import PurePosixPath


class ArtifactError(ValueError):
    pass


def normalize_archive(src_tar: str, dst_gz: str, max_bytes: int, max_files: int) -> tuple[int, int]:
    """src_tar(디렉터리 하나를 담은 tar)를 검증하고 최상위 디렉터리를 벗겨 dst_gz 로 쓴다. 반환: (파일 수, 풀었을 때 총 크기).

    거부: 절대 경로, '..' 포함 경로, 디렉터리 밖을 가리키는 심볼릭·하드 링크, 장치·FIFO. node_modules 의 상대 심볼릭 링크는 허용한다.
    """
    files = total = 0
    with tarfile.open(src_tar) as tin, gzip.open(dst_gz, "wb", compresslevel=6) as gz, tarfile.open(fileobj=gz, mode="w") as tout:
        for m in tin:
            name = m.name
            if name.startswith("/") or ".." in PurePosixPath(name).parts:
                raise ArtifactError(f"허용되지 않는 경로: {name}")
            rest = PurePosixPath(name).parts[1:]
            if not rest:
                continue  # 최상위 디렉터리 자체
            if m.isdev() or m.isfifo():
                raise ArtifactError(f"장치·FIFO 파일은 배포할 수 없습니다: {name}")
            new = "/".join(rest)
            if m.issym():
                if m.linkname.startswith("/"):
                    raise ArtifactError(f"절대 경로 심볼릭 링크는 배포할 수 없습니다: {name}")
                target = posixpath.normpath(posixpath.join(posixpath.dirname(new), m.linkname))
                if target == ".." or target.startswith("../"):
                    raise ArtifactError(f"디렉터리 밖을 가리키는 심볼릭 링크: {name}")
            elif m.islnk():
                lp = PurePosixPath(m.linkname).parts
                if m.linkname.startswith("/") or ".." in lp or len(lp) < 2:
                    raise ArtifactError(f"허용되지 않는 하드 링크: {name}")
                m.linkname = "/".join(lp[1:])
            files += 1
            total += m.size if m.isfile() else 0
            if files > max_files:
                raise ArtifactError(f"파일이 너무 많습니다 (최대 {max_files}개)")
            if total > max_bytes:
                raise ArtifactError(f"배포 크기가 제한을 넘었습니다 (최대 {max_bytes // (1024 * 1024)}MB)")
            m.name = new
            m.uid = m.gid = 1000
            m.uname = m.gname = ""
            tout.addfile(m, tin.extractfile(m) if m.isfile() else None)
    if files == 0:
        raise ArtifactError("배포할 파일이 없습니다 (빈 디렉터리)")
    return files, total


# 컨테이너 안에서 정적 파일을 서비스하는 서버: SPA 라우팅 폴백(확장자 없는 없는 경로 → index.html), 디렉터리 목록 없음, 경로 이탈 차단
STATIC_SERVER_PY = '''import http.server, os, socketserver, sys

PORT = int(sys.argv[1])
ROOT = os.path.realpath(sys.argv[2])


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def send_head(self):
        path = self.translate_path(self.path)
        last = self.path.split("?")[0].rstrip("/").split("/")[-1]
        if not os.path.exists(path) and "." not in last:
            self.path = "/index.html"
        return super().send_head()

    def list_directory(self, path):
        self.send_error(404, "Not Found")

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, *a):
        pass


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


Server(("0.0.0.0", PORT), Handler).serve_forever()
'''
