"""Telegram 게이트웨이: 사용자별 봇을 long polling 으로 받아 에이전트에 전달하고 답을 돌려준다.

- 봇 등록·해제는 CHANNEL_SYNC_SECONDS 주기로 반영한다 (사용자별 AccountWorker 하나).
- 같은 봇을 여러 프로세스가 동시에 polling 하지 않도록 Redis 잠금을 건다 (Redis 가 없으면 잠금 없이 동작).
- 연결되지 않은 Telegram 계정의 메시지는 /start <코드> 외에는 응답하지 않는다.
"""
import asyncio
import json
import logging
import uuid
from datetime import date
from typing import Optional

from app.channels.telegram_api import TelegramClient, TelegramError
from app.channels.telegram_format import render_messages, table_widget_text
from app.config import settings
from app.core.crypto import decrypt
from app.core.runs import RunRegistry, cancellable_events
from app.db.session import AsyncSessionLocal
from app.models.channel_account import ChannelAccount

logger = logging.getLogger(__name__)

CANCEL_NOTE = "_(사용자가 실행을 중단했습니다)_"
HELP = (
    "사용 가능한 명령\n"
    "/new — 새 대화 시작\n"
    "/stop — 실행 중인 작업 중단\n"
    "/status — 연결·대화 상태\n"
    "/help — 도움말\n\n"
    "그 외 메시지는 에이전트에게 전달됩니다. 코드 실행·파일 변경·외부 도구 호출 전에는 허용 버튼이 나타납니다. "
    "현재는 텍스트 메시지만 지원합니다."
)
_LOCK_TTL = 60
_instance = uuid.uuid4().hex
_daily: dict[tuple[str, date], int] = {}


# ─── Redis 잠금 ───────────────────────────────────────────────────────────────

async def _lock(account_id: str) -> bool:
    """이 프로세스가 봇의 polling 권한을 갖는지. Redis 사용 불가 시 True (단일 프로세스로 간주)."""
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL)
        try:
            key = f"claw:tg:{account_id}"
            if await r.set(key, _instance, nx=True, ex=_LOCK_TTL):
                return True
            if (await r.get(key) or b"").decode() == _instance:
                await r.expire(key, _LOCK_TTL)
                return True
            return False
        finally:
            await r.aclose()
    except Exception:  # noqa: BLE001
        logger.warning("[channels] Redis 잠금 불가 — 잠금 없이 진행")
        return True


# ─── 발신 ─────────────────────────────────────────────────────────────────────

async def send_markdown(client: TelegramClient, chat_id: int, text: str) -> None:
    for html_text, plain in render_messages(text):
        for attempt in range(2):
            try:
                try:
                    await client.send_message(chat_id, html_text)
                except TelegramError as e:
                    if e.status == 400:  # HTML 해석 실패 → 서식 없이
                        await client.send_message(chat_id, plain, html=False)
                    else:
                        raise
                break
            except TelegramError as e:
                if e.status == 429 and attempt == 0:
                    await asyncio.sleep(3)
                    continue
                logger.warning("[channels] 전송 실패: %s", e)
                return


def _widget_notes(steps: list[dict], answer: str) -> str:
    """위젯은 Telegram 에서 그릴 수 없다. 표는 본문에 같은 표가 없을 때만 텍스트로, 나머지는 웹 안내."""
    notes = []
    has_table = any(line.lstrip().startswith("|") for line in answer.split("\n"))
    for s in steps:
        if s.get("type") != "tool_result" or s.get("tool") != "create_widget":
            continue
        try:
            w = (json.loads(s.get("output") or "{}") or {}).get("widget") or {}
        except ValueError:
            continue
        if not w:
            continue
        if w.get("type") == "table" and not has_table:
            notes.append(table_widget_text(w.get("spec") or {}))
        elif w.get("type") != "table":
            notes.append(f"📊 {w.get('title') or w.get('type')} — 차트·도식은 웹에서 확인하세요.")
    return "\n\n".join(n for n in notes if n)


# ─── 계정별 작업자 ────────────────────────────────────────────────────────────

class AccountWorker:
    def __init__(self, account_id: str, token: str, token_enc: str):
        self.account_id = account_id
        self.token_enc = token_enc
        self.client = TelegramClient(token)
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=settings.CHANNEL_QUEUE_MAX)
        self.busy = False
        self.pending: dict[str, asyncio.Future] = {}  # 승인 요청 id → 결과 (True=허용, False=거부)
        self.auto_allow: set[str] = set()  # '이번 대화 모두 허용'을 누른 대화
        self.tasks: list[asyncio.Task] = []
        self._current_conv: Optional[str] = None

    def start(self) -> None:
        self.tasks = [asyncio.create_task(self._poll()), asyncio.create_task(self._consume())]

    async def stop(self) -> None:
        for t in self.tasks:
            t.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await self.client.aclose()

    # 수신 ----------------------------------------------------------------
    async def _poll(self) -> None:
        backoff = 1
        while True:
            try:
                if not await _lock(self.account_id):
                    await asyncio.sleep(_LOCK_TTL / 2)
                    continue
                async with AsyncSessionLocal() as db:
                    acc = await db.get(ChannelAccount, self.account_id)
                    if acc is None or not acc.enabled:
                        return
                    offset = (acc.last_update_id or 0) + 1
                updates = await self.client.get_updates(offset)
                backoff = 1
                for upd in updates:
                    try:
                        await self._handle_update(upd)
                    except Exception:  # noqa: BLE001
                        logger.exception("[channels] update 처리 실패 account=%s", self.account_id)
                    await self._save_offset(upd["update_id"])
            except asyncio.CancelledError:
                raise
            except TelegramError as e:
                if e.status == 401:  # 토큰 폐기
                    await self._set_error("봇 토큰이 유효하지 않습니다 (BotFather 에서 폐기됨?)")
                    return
                if e.status == 409:  # 다른 곳에서 polling/webhook 사용 중
                    await self._set_error("다른 곳에서 이 봇을 사용 중입니다 (webhook 또는 다른 서버)")
                    try:
                        await self.client.delete_webhook()
                    except TelegramError:
                        pass
                logger.warning("[channels] polling 오류 account=%s: %s", self.account_id, e)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
            except Exception:  # noqa: BLE001
                logger.exception("[channels] polling 예외 account=%s", self.account_id)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    async def _save_offset(self, update_id: int) -> None:
        async with AsyncSessionLocal() as db:
            acc = await db.get(ChannelAccount, self.account_id)
            if acc and update_id > (acc.last_update_id or 0):
                acc.last_update_id = update_id
                await db.commit()

    async def _set_error(self, message: str) -> None:
        async with AsyncSessionLocal() as db:
            acc = await db.get(ChannelAccount, self.account_id)
            if acc:
                acc.status, acc.last_error = "error", message[:500]
                await db.commit()

    async def _handle_callback(self, cb: dict) -> None:
        """승인 버튼 응답. 연결된 소유자의 것만 받는다."""
        async with AsyncSessionLocal() as db:
            acc = await db.get(ChannelAccount, self.account_id)
            owner = acc.external_user_id if acc else None
        if owner is None or (cb.get("from") or {}).get("id") != owner:
            return
        parts = (cb.get("data") or "").split(":")
        fut = self.pending.get(parts[1]) if len(parts) == 3 and parts[0] == "ap" else None
        if fut is None or fut.done():
            await self.client.answer_callback(cb["id"], "이미 처리되었거나 만료된 요청입니다")
            return
        fut.set_result(parts[2] in ("a", "s"))
        if parts[2] == "s":
            self.auto_allow.add(self._current_conv or "")
        await self.client.answer_callback(cb["id"], "허용" if parts[2] in ("a", "s") else "거부")

    async def _approve(self, chat_id: int, tool: str, summary: str) -> bool:
        """위험 도구 실행 전 버튼으로 묻는다. 시간 초과·오류는 거부로 처리한다."""
        if self._current_conv in self.auto_allow:
            return True
        rid = uuid.uuid4().hex[:8]
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self.pending[rid] = fut
        markup = {"inline_keyboard": [[
            {"text": "✅ 허용", "callback_data": f"ap:{rid}:a"},
            {"text": "✅ 이 대화 모두 허용", "callback_data": f"ap:{rid}:s"},
            {"text": "⛔ 거부", "callback_data": f"ap:{rid}:d"},
        ]]}
        msg_id = None
        try:
            sent = await self.client.send_message(chat_id, f"🔐 승인 요청 · {tool}\n\n{summary}", html=False, reply_markup=markup)
            msg_id = sent["message_id"]
            allowed = await asyncio.wait_for(fut, settings.CHANNEL_APPROVAL_TIMEOUT_SECONDS)
        except (asyncio.TimeoutError, TelegramError):
            allowed = False
        finally:
            self.pending.pop(rid, None)
            if msg_id is not None:  # 버튼을 지우고 결과를 남긴다
                try:
                    await self.client.edit_message(chat_id, msg_id, f"{'✅ 허용됨' if fut.done() and not fut.cancelled() and fut.result() else '⛔ 거부됨/만료'} · {tool}")
                except Exception:  # noqa: BLE001
                    pass
        return allowed

    async def _handle_update(self, upd: dict) -> None:
        if upd.get("callback_query"):
            await self._handle_callback(upd["callback_query"])
            return
        msg = upd.get("message")
        if not msg or (msg.get("chat") or {}).get("type") != "private":
            return
        chat_id = msg["chat"]["id"]
        sender = (msg.get("from") or {}).get("id")
        text = (msg.get("text") or "").strip()

        async with AsyncSessionLocal() as db:
            acc = await db.get(ChannelAccount, self.account_id)
            if acc is None:
                return
            if acc.external_user_id is None:  # 아직 연결 전: /start <코드> 만 받는다
                parts = text.split(maxsplit=1)
                if parts and parts[0].split("@")[0] == "/start" and len(parts) == 2:
                    from app.services.channel_service import ChannelService

                    if ChannelService.try_pair(acc, parts[1], sender, chat_id):
                        await db.commit()
                        await send_markdown(self.client, chat_id, "✅ 연결되었습니다. 이제 메시지를 보내면 에이전트가 답합니다.\n\n" + HELP)
                    else:
                        await send_markdown(self.client, chat_id, "연결 코드가 올바르지 않거나 만료되었습니다. 웹에서 새 코드를 발급하세요.")
                return
            if sender != acc.external_user_id:
                return  # 연결된 소유자 외에는 존재를 알리지 않는다
            user_id = acc.user_id

        if not text:
            await send_markdown(self.client, chat_id, "아직 텍스트 메시지만 지원합니다.")
            return
        cmd = text.split()[0].split("@")[0].lower() if text.startswith("/") else ""
        if cmd == "/stop":
            await self._stop(chat_id, user_id)
        elif cmd in ("/help", "/start"):
            await send_markdown(self.client, chat_id, HELP)
        elif cmd == "/status":
            await self._status(chat_id)
        elif cmd == "/new":
            if self.busy or RunRegistry.is_running(await self._conversation_id() or ""):
                await send_markdown(self.client, chat_id, "작업이 실행 중입니다. /stop 으로 중단한 뒤 다시 시도하세요.")
            else:
                await self._new_conversation(chat_id)
        else:
            key = (user_id, date.today())
            if _daily.get(key, 0) >= settings.CHANNEL_DAILY_MESSAGE_LIMIT:
                await send_markdown(self.client, chat_id, "오늘 처리할 수 있는 메시지 수를 초과했습니다.")
                return
            _daily[key] = _daily.get(key, 0) + 1
            if self.busy:
                await send_markdown(self.client, chat_id, f"⏳ 앞선 작업이 끝나면 처리합니다 (대기 {self.queue.qsize() + 1}건).")
            try:
                self.queue.put_nowait((chat_id, user_id, text))
            except asyncio.QueueFull:
                await send_markdown(self.client, chat_id, "대기 중인 메시지가 너무 많습니다. 잠시 후 다시 보내세요.")

    # 명령 ----------------------------------------------------------------
    async def _conversation_id(self) -> Optional[str]:
        async with AsyncSessionLocal() as db:
            acc = await db.get(ChannelAccount, self.account_id)
            return acc.conversation_id if acc else None

    async def _stop(self, chat_id: int, user_id: str) -> None:
        dropped = 0
        while not self.queue.empty():  # 대기 중인 메시지도 함께 비운다
            self.queue.get_nowait()
            dropped += 1
        cid = await self._conversation_id()
        if cid and RunRegistry.cancel(cid, user_id):
            return  # 취소 결과는 실행 쪽에서 알린다
        await send_markdown(self.client, chat_id, "실행 중인 작업이 없습니다." + (f" (대기 {dropped}건 취소)" if dropped else ""))

    async def _status(self, chat_id: int) -> None:
        async with AsyncSessionLocal() as db:
            acc = await db.get(ChannelAccount, self.account_id)
            from app.models.conversation import Conversation

            conv = await db.get(Conversation, acc.conversation_id) if acc and acc.conversation_id else None
        running = bool(conv and RunRegistry.is_running(conv.id))
        await send_markdown(
            self.client, chat_id,
            f"연결됨 · 현재 대화: {conv.title if conv else '(없음 — 메시지를 보내면 만들어집니다)'}\n"
            f"상태: {'실행 중' if running else '대기'} · 대기열 {self.queue.qsize()}건",
        )

    async def _new_conversation(self, chat_id: int) -> None:
        async with AsyncSessionLocal() as db:
            acc = await db.get(ChannelAccount, self.account_id)
            conv = await _create_conversation(acc, db)
            acc.conversation_id = conv.id
            await db.commit()
        await send_markdown(self.client, chat_id, "🆕 새 대화를 시작합니다.")

    # 실행 ----------------------------------------------------------------
    async def _consume(self) -> None:
        while True:
            chat_id, user_id, text = await self.queue.get()
            self.busy = True
            try:
                async with asyncio.timeout(settings.CHANNEL_RUN_TIMEOUT_SECONDS + 30):
                    await self._run_turn(chat_id, user_id, text)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                logger.exception("[channels] 실행 실패 account=%s", self.account_id)
                await send_markdown(self.client, chat_id, f"⚠️ 오류가 발생했습니다: {type(e).__name__}")
            finally:
                self.busy = False

    async def _run_turn(self, chat_id: int, user_id: str, text: str) -> None:
        from app.agent.agent_runtime import memory_enabled
        from app.models.conversation import Conversation
        from app.agent.orchestrator import AgentOrchestrator
        from app.services.agent_service import AgentService
        from app.services.chat_service import ChatService

        async with AsyncSessionLocal() as db:
            acc = await db.get(ChannelAccount, self.account_id)
            conv = await db.get(Conversation, acc.conversation_id) if acc.conversation_id else None
            if conv is None or conv.user_id != user_id:
                conv = await _create_conversation(acc, db)
                acc.conversation_id = conv.id
                await db.commit()
            conv_id = conv.id
            if RunRegistry.is_running(conv_id):  # 웹에서 같은 대화를 쓰는 중
                await send_markdown(self.client, chat_id, "이 대화가 웹에서 실행 중입니다. 잠시 후 다시 보내세요.")
                return
            runtime = await AgentService.runtime_for_conversation(conv, db)
            await ChatService.save_message(conv_id, "user", text, db)

            self._current_conv = conv_id

            async def approver(tool: str, summary: str) -> bool:
                return await self._approve(chat_id, tool, summary)

            orchestrator = AgentOrchestrator(
                user_id,
                runtime=runtime,
                llm_provider=conv.llm_provider,
                model=conv.model_name,
                user_timezone=settings.SCHEDULER_DEFAULT_TIMEZONE,
                channel=True,
                approver=approver,
                allow_mcp=settings.CHANNEL_ALLOW_MCP,
                allow_browser=settings.CHANNEL_ALLOW_BROWSER,
            )
            answer, steps, error, cancelled = "", [], None, False
            status_id: Optional[int] = None
            last_edit = 0.0
            typing = asyncio.create_task(self._typing_loop(chat_id))
            try:
                async with asyncio.timeout(settings.CHANNEL_RUN_TIMEOUT_SECONDS):
                    async for ev in cancellable_events(conv_id, user_id, orchestrator.run(text, conv_id, db)):
                        t = ev.get("type")
                        if t == "token":
                            answer += ev.get("content", "")
                        elif t in ("thought", "tool_call", "tool_result"):
                            steps.append(ev)
                            if t == "tool_call":
                                now = asyncio.get_running_loop().time()
                                label = f"🔧 {ev.get('tool')} 실행 중…"
                                try:
                                    if status_id is None:
                                        status_id = (await self.client.send_message(chat_id, label, html=False))["message_id"]
                                        last_edit = now
                                    elif now - last_edit >= 2.0:  # 메시지 수정은 빈도 제한이 있다
                                        await self.client.edit_message(chat_id, status_id, label)
                                        last_edit = now
                                except TelegramError:
                                    pass
                        elif t == "error":
                            error = ev.get("message") or "에이전트 오류"
                        elif t == "cancelled":
                            cancelled = True
            except TimeoutError:
                error = f"제한 시간({settings.CHANNEL_RUN_TIMEOUT_SECONDS}초)을 초과했습니다"
            finally:
                typing.cancel()
                if status_id is not None:
                    await self.client.delete_message(chat_id, status_id)

            if cancelled:
                saved = answer + ("\n\n" if answer else "") + CANCEL_NOTE
                await ChatService.save_message(conv_id, "assistant", saved, db, agent_steps=steps)
                await send_markdown(self.client, chat_id, (answer + "\n\n" if answer else "") + "⏹ 실행을 중단했습니다.")
                return
            if error and not answer:
                await ChatService.save_message(conv_id, "assistant", "__error__", db, agent_steps=steps)
                await send_markdown(self.client, chat_id, f"⚠️ {error}")
                return
            if not answer.strip():
                await send_markdown(self.client, chat_id, "응답을 만들지 못했습니다.")
                return
            await ChatService.save_message(conv_id, "assistant", answer, db, agent_steps=steps)
            extra = _widget_notes(steps, answer)
            await send_markdown(self.client, chat_id, answer + (f"\n\n{extra}" if extra else ""))

            from app.services.conversation_summary import maybe_update_summary

            asyncio.create_task(maybe_update_summary(conv_id))
            if memory_enabled(runtime) and not error:
                from app.services.memory_extractor import maybe_extract_memories

                async with AsyncSessionLocal() as mem_db:
                    await maybe_extract_memories(
                        user_id=user_id, conversation_id=conv_id, user_message=text, agent_response=answer, db=mem_db
                    )

    async def _typing_loop(self, chat_id: int) -> None:
        while True:
            await self.client.typing(chat_id)
            await asyncio.sleep(4)


async def _create_conversation(acc: ChannelAccount, db):
    from app.schemas.chat import ConversationCreate
    from app.services.chat_service import ChatService

    conv = await ChatService.create_conversation(acc.user_id, ConversationCreate(title="[Telegram] 새 대화"), db)
    conv.channel = acc.channel
    await db.commit()
    return conv


# ─── 관리자 루프 ──────────────────────────────────────────────────────────────

async def run_channels() -> None:
    """활성 봇마다 AccountWorker 를 띄우고, 등록·해제·토큰 교체를 주기적으로 반영한다."""
    from sqlalchemy import select

    workers: dict[str, AccountWorker] = {}
    try:
        while True:
            try:
                async with AsyncSessionLocal() as db:
                    rows = (await db.execute(select(ChannelAccount).where(ChannelAccount.enabled.is_(True), ChannelAccount.status != "error"))).scalars().all()
                wanted = {a.id: a for a in rows}
                for aid in list(workers):
                    w = workers[aid]
                    if aid not in wanted or wanted[aid].token_enc != w.token_enc or all(t.done() for t in w.tasks):
                        await w.stop()
                        del workers[aid]
                for aid, a in wanted.items():
                    if aid not in workers:
                        try:
                            workers[aid] = AccountWorker(aid, decrypt(a.token_enc), a.token_enc)
                        except ValueError as e:
                            logger.error("[channels] %s", e)
                            continue
                        workers[aid].start()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("[channels] 동기화 실패")
            await asyncio.sleep(settings.CHANNEL_SYNC_SECONDS)
    finally:
        for w in workers.values():
            await w.stop()
