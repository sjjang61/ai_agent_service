"""Telegram Bot API 최소 클라이언트 (httpx). 토큰은 로그·예외 메시지에 남기지 않는다."""
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)
API = "https://api.telegram.org"


class TelegramError(Exception):
    def __init__(self, method: str, status: int, description: str):
        super().__init__(f"{method}: {status} {description}")
        self.method, self.status, self.description = method, status, description


class TelegramClient:
    def __init__(self, token: str, http: Optional[httpx.AsyncClient] = None):
        self._token = token
        self._http = http or httpx.AsyncClient(timeout=httpx.Timeout(40.0, connect=10.0))
        self._owns_http = http is None

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def call(self, method: str, timeout: Optional[float] = None, **params: Any) -> Any:
        try:
            r = await self._http.post(f"{API}/bot{self._token}/{method}", json=params, timeout=timeout)
        except httpx.HTTPError as e:  # URL(=토큰)이 메시지에 섞이지 않게 형식만 남긴다
            raise TelegramError(method, 0, f"네트워크 오류 {type(e).__name__}") from None
        try:
            body = r.json()
        except ValueError:
            raise TelegramError(method, r.status_code, "JSON 이 아닌 응답") from None
        if not body.get("ok"):
            raise TelegramError(method, r.status_code, str(body.get("description", "")))
        return body.get("result")

    async def get_me(self) -> dict:
        return await self.call("getMe")

    async def get_updates(self, offset: int, timeout: int = 25) -> list[dict]:
        # `timeout` 은 Telegram 의 long-poll 대기 시간(초)이고 HTTP 타임아웃은 그보다 길어야 한다
        return await self.call("getUpdates", float(timeout + 15), offset=offset, allowed_updates=["message", "callback_query"], **{"timeout": timeout})

    async def delete_webhook(self) -> None:
        await self.call("deleteWebhook", drop_pending_updates=False)

    async def send_message(self, chat_id: int, text: str, html: bool = True, reply_markup: Optional[dict] = None) -> dict:
        params: dict = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
        if reply_markup:
            params["reply_markup"] = reply_markup
        if html:
            params["parse_mode"] = "HTML"
        return await self.call("sendMessage", **params)

    async def edit_message(self, chat_id: int, message_id: int, text: str) -> None:
        try:
            await self.call("editMessageText", chat_id=chat_id, message_id=message_id, text=text)
        except TelegramError as e:
            if "not modified" not in e.description:
                raise

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        try:
            await self.call("deleteMessage", chat_id=chat_id, message_id=message_id)
        except TelegramError:
            pass

    async def typing(self, chat_id: int) -> None:
        try:
            await self.call("sendChatAction", chat_id=chat_id, action="typing")
        except TelegramError:
            pass

    async def answer_callback(self, callback_id: str, text: str = "") -> None:
        try:
            await self.call("answerCallbackQuery", callback_query_id=callback_id, text=text)
        except TelegramError:
            pass
