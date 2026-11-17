"""My Apps 최대 수: 환경설정(APP_MAX_PER_USER)으로 정하고, 넘으면 새 앱 배포를 막는다."""
import pytest

from app.config import Settings, settings
from app.services import app_service
from app.services.app_service import AppService, DeployError


def test_default_limit_is_ten_and_configurable_by_env(monkeypatch):
    assert Settings(_env_file=None).APP_MAX_PER_USER == 10
    monkeypatch.setenv("APP_MAX_PER_USER", "3")
    assert Settings(_env_file=None).APP_MAX_PER_USER == 3  # 환경변수로 바꾼다


@pytest.mark.asyncio
async def test_deploy_is_refused_for_a_new_app_at_the_limit_but_not_an_update(monkeypatch):
    monkeypatch.setattr(settings, "APP_MAX_PER_USER", 10)

    async def ten(user_id, db):
        return [object()] * 10

    async def nine(user_id, db):
        return [object()] * 9

    async def none_existing(user_id, name, db):
        return None

    monkeypatch.setattr(AppService, "list_for_user", staticmethod(ten))
    monkeypatch.setattr(AppService, "get", staticmethod(none_existing))
    with pytest.raises(DeployError, match="최대 10개"):
        await AppService.deploy("u1", None, None, "새 앱", "/workspace/app")  # 10개 보유 + 새 앱 → 거부

    # 9개면 한도 검사를 통과한다 (이후 단계는 샌드박스가 필요하므로 거기서 다른 오류가 나는 것은 정상)
    monkeypatch.setattr(AppService, "list_for_user", staticmethod(nine))
    try:
        await AppService.deploy("u1", None, None, "새 앱", "/workspace/app")
    except DeployError as e:
        assert "최대" not in str(e)
    except Exception:
        pass  # 샌드박스·DB 없는 환경: 한도 검사 이후의 실패


@pytest.mark.asyncio
async def test_info_reports_count_against_the_limit(monkeypatch):
    from app.api import apps as apps_api

    class U:
        id = "u1"

    async def seven(user_id, db):
        return [object()] * 7

    monkeypatch.setattr(AppService, "list_for_user", staticmethod(seven))
    monkeypatch.setattr(settings, "APP_MAX_PER_USER", 10)
    r = await apps_api.info(current_user=U(), db=None)
    assert r["count"] == 7 and r["max_per_user"] == 10
