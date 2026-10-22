import re
from datetime import datetime, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.space import Page, Space
from app.models.user import User
from app.schemas.space import (
    PageCreate,
    PageResponse,
    PageSummary,
    PageUpdate,
    SpaceInput,
    SpaceResponse,
)
from app.services.schedule_service import aware

router = APIRouter()

MAX_SPACES_PER_USER = 50
MAX_PAGES_PER_USER = 2000


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _snippet(content: str) -> str:
    text = re.sub(r"[#>*`_\[\]\-|]+", " ", content or "")
    return " ".join(text.split())[:120]


def _summary(p: Page) -> dict:
    return dict(
        id=p.id, title=p.title, snippet=_snippet(p.content), space_id=p.space_id,
        is_favorite=bool(p.is_favorite), deleted_at=aware(p.deleted_at),
        created_at=aware(p.created_at), updated_at=aware(p.updated_at),
    )


async def _own_page(page_id: str, user: User, db: AsyncSession) -> Page:
    r = await db.execute(select(Page).where(Page.id == page_id, Page.user_id == user.id))
    page = r.scalar_one_or_none()
    if not page:
        raise HTTPException(404, "페이지를 찾을 수 없습니다")
    return page


async def _check_space(space_id: Optional[str], user: User, db: AsyncSession) -> None:
    if space_id is None:
        return
    r = await db.execute(select(Space.id).where(Space.id == space_id, Space.user_id == user.id))
    if r.scalar_one_or_none() is None:
        raise HTTPException(404, "공간을 찾을 수 없습니다")


# ---------------- spaces ----------------


@router.get("/spaces", response_model=List[SpaceResponse])
async def list_spaces(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    counts = dict(
        (await db.execute(
            select(Page.space_id, func.count()).where(
                Page.user_id == user.id, Page.deleted_at.is_(None), Page.space_id.is_not(None)
            ).group_by(Page.space_id)
        )).all()
    )
    rows = (await db.execute(select(Space).where(Space.user_id == user.id).order_by(Space.created_at))).scalars().all()
    return [SpaceResponse(id=s.id, name=s.name, page_count=counts.get(s.id, 0)) for s in rows]


@router.post("/spaces", response_model=SpaceResponse)
async def create_space(data: SpaceInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    n = (await db.execute(select(func.count()).select_from(Space).where(Space.user_id == user.id))).scalar_one()
    if n >= MAX_SPACES_PER_USER:
        raise HTTPException(400, f"공간은 최대 {MAX_SPACES_PER_USER}개까지 만들 수 있습니다")
    space = Space(user_id=user.id, name=data.name.strip())
    db.add(space)
    await db.commit()
    return SpaceResponse(id=space.id, name=space.name)


@router.put("/spaces/{space_id}", response_model=SpaceResponse)
async def rename_space(space_id: str, data: SpaceInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    await _check_space(space_id, user, db)
    await db.execute(update(Space).where(Space.id == space_id, Space.user_id == user.id).values(name=data.name.strip()))
    await db.commit()
    return SpaceResponse(id=space_id, name=data.name.strip())


@router.delete("/spaces/{space_id}")
async def delete_space(space_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """공간만 삭제하고 안의 페이지는 '공간 없음' 으로 남긴다."""
    await _check_space(space_id, user, db)
    await db.execute(update(Page).where(Page.user_id == user.id, Page.space_id == space_id).values(space_id=None))
    await db.execute(delete(Space).where(Space.id == space_id, Space.user_id == user.id))
    await db.commit()
    return {"status": "deleted"}


# ---------------- pages ----------------


@router.get("/pages", response_model=List[PageSummary])
async def list_pages(
    view: Literal["all", "favorites", "trash"] = "all",
    space_id: Optional[str] = None,
    q: Optional[str] = Query(default=None, max_length=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    stmt = select(Page).where(Page.user_id == user.id)
    stmt = stmt.where(Page.deleted_at.is_not(None) if view == "trash" else Page.deleted_at.is_(None))
    if view == "favorites":
        stmt = stmt.where(Page.is_favorite.is_(True))
    if space_id:
        stmt = stmt.where(Page.space_id == space_id)
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Page.title.like(like), Page.content.like(like)))
    rows = (await db.execute(stmt.order_by(Page.updated_at.desc()).limit(500))).scalars().all()
    return [PageSummary(**_summary(p)) for p in rows]


@router.post("/pages", response_model=PageResponse)
async def create_page(data: PageCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    await _check_space(data.space_id, user, db)
    n = (await db.execute(select(func.count()).select_from(Page).where(Page.user_id == user.id))).scalar_one()
    if n >= MAX_PAGES_PER_USER:
        raise HTTPException(400, f"페이지는 최대 {MAX_PAGES_PER_USER}개까지 만들 수 있습니다")
    page = Page(user_id=user.id, title=data.title.strip(), content=data.content, space_id=data.space_id)
    db.add(page)
    await db.commit()
    await db.refresh(page)
    return PageResponse(**_summary(page), content=page.content)


@router.get("/pages/{page_id}", response_model=PageResponse)
async def get_page(page_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    page = await _own_page(page_id, user, db)
    return PageResponse(**_summary(page), content=page.content)


@router.put("/pages/{page_id}", response_model=PageResponse)
async def update_page(page_id: str, data: PageUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    page = await _own_page(page_id, user, db)
    if page.deleted_at is not None:
        raise HTTPException(409, "휴지통의 페이지는 수정할 수 없습니다. 먼저 복원하세요")
    if data.title is not None:
        page.title = data.title.strip()
    if data.content is not None:
        page.content = data.content
    if data.is_favorite is not None:
        page.is_favorite = data.is_favorite
    if data.clear_space:
        page.space_id = None
    elif data.space_id is not None:
        await _check_space(data.space_id, user, db)
        page.space_id = data.space_id
    page.updated_at = _now()
    await db.commit()
    await db.refresh(page)
    return PageResponse(**_summary(page), content=page.content)


@router.delete("/pages/{page_id}")
async def trash_page(page_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """휴지통으로 이동 (soft delete)"""
    page = await _own_page(page_id, user, db)
    page.deleted_at = _now()
    await db.commit()
    return {"status": "trashed"}


@router.post("/pages/{page_id}/restore", response_model=PageSummary)
async def restore_page(page_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    page = await _own_page(page_id, user, db)
    page.deleted_at = None
    page.updated_at = _now()
    await db.commit()
    await db.refresh(page)
    return PageSummary(**_summary(page))


@router.delete("/pages/{page_id}/permanent")
async def delete_page_permanently(page_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    page = await _own_page(page_id, user, db)
    if page.deleted_at is None:
        raise HTTPException(409, "휴지통에 있는 페이지만 영구 삭제할 수 있습니다")
    await db.delete(page)
    await db.commit()
    return {"status": "deleted"}


@router.delete("/trash")
async def empty_trash(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    r = await db.execute(delete(Page).where(Page.user_id == user.id, Page.deleted_at.is_not(None)))
    await db.commit()
    return {"deleted": r.rowcount}
