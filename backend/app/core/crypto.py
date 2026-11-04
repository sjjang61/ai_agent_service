"""저장용 비밀값(봇 토큰 등) 대칭 암호화. SECRET_KEY 에서 키를 파생한다 (키가 바뀌면 복호화되지 않는다)."""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest()))


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise ValueError("저장된 비밀값을 복호화할 수 없습니다 (SECRET_KEY 변경?)") from e
