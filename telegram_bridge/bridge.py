"""Telegram <-> n8n bridge using Bot API long polling.

Long polling needs no public URL, tunnel or open port: the bridge pulls updates from Telegram,
forwards each message to the n8n assistant webhook (which orchestrates the agents) and sends the
returned text back to the chat.

Privacy: message texts, files and chat identifiers are never logged or written to disk. Files are
downloaded into memory, base64-encoded for the webhook, and discarded. Errors are logged by
exception type only, because httpx error messages contain the request URL (and thus the token).
"""

import base64
import logging
import threading
import time
from pathlib import Path
from telegram_bridge.contracts import AssistantRequest, AssistantResponse
from telegram_bridge.dossier import render_dossier
from telegram_bridge.ui import TEXT, COMMANDS, PROCEDURES, keyboard, language_keyboard, main_keyboard, navigation, BUSY

import httpx

log = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
MAX_MESSAGE_CHARS = 4000  # Telegram limit is 4096
POLL_TIMEOUT_SECONDS = 30
SUPPORTED_DOCUMENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}
TELEGRAM_LANGUAGES = {"fr": "fr", "ar": "ar", "en": "en"}

ERROR_TEXT = {
    "en": "Sorry, the assistant is temporarily unavailable. Please try again later.",
    "fr": "Désolé, l'assistant est momentanément indisponible. Veuillez réessayer plus tard.",
    "ar": "عذرا، المساعد غير متاح حاليا. يرجى المحاولة لاحقا.",
    "derja": "سامحني، المساعد موش متوفر توا. عاود جرّب بعد شوية.",
}
UNSUPPORTED_TEXT = {
    "en": "Please send a question as text, or a form as a photo, an image or a PDF (max {mb} MB).",
    "fr": "Envoyez une question sous forme de texte, ou un formulaire en photo, image ou PDF (max {mb} Mo).",
    "ar": "أرسل سؤالك نصا، أو المطبوعة في شكل صورة أو ملف PDF (الحد الأقصى {mb} ميغابايت).",
    "derja": "ابعث سؤالك نص ولا مطبوعة PDF ولا JPEG ولا PNG (حتى {mb} ميغابايت).",
}


def split_message(text: str, limit: int = MAX_MESSAGE_CHARS) -> list[str]:
    """Split plain text within Telegram UTF-16 message limits."""
    if limit < 2:
        raise ValueError("Message limit must be at least two UTF-16 units")
    parts, current, units = [], "", 0
    for char in text:
        width = 2 if ord(char) > 0xFFFF else 1
        if units + width > limit:
            parts.append(current)
            current, units = "", 0
        current += char
        units += width
    if current:
        parts.append(current)
    return parts or [""]



class TelegramBridge:
    def __init__(self, token: str, webhook_url: str, max_upload_bytes: int,
                 client: httpx.Client | None = None, webhook_timeout: float = 900.0, dialogue_enabled: bool = False):
        if not token or not token.strip():
            raise ValueError("TELEGRAM_BOT_TOKEN is not set")
        self._base = f"{TELEGRAM_API}/bot{token}"
        self._file_base = f"{TELEGRAM_API}/file/bot{token}"
        self.webhook_url = webhook_url
        self.max_upload_bytes = max_upload_bytes
        self.client = client or httpx.Client(timeout=POLL_TIMEOUT_SECONDS + 15)
        self.webhook_timeout = webhook_timeout
        self.dialogue_enabled = dialogue_enabled
        self.offset: int | None = None
        self.sessions = {}
        self.inflight = {}
        self._state_lock = threading.RLock()
        self.stop = threading.Event()
        self.last_poll = time.monotonic()
        # HTTP libraries can otherwise emit token-bearing URLs at INFO/DEBUG.
        logging.getLogger("httpx").setLevel(logging.CRITICAL)
        logging.getLogger("httpcore").setLevel(logging.CRITICAL)

    @staticmethod
    def session_key(message: dict, sender: dict | None = None):
        """Private chats keep one session per chat. In groups every member gets an isolated session, so one
        member's procedure, language or dialogue context never reaches another. Only Telegram's numeric
        user id is used (no names or usernames); replies still go to the chat."""
        chat = message["chat"]
        if chat.get("type", "private") == "private":
            return chat["id"]
        user = (sender if sender is not None else message.get("from")) or {}
        return (chat["id"], user.get("id"))

    def session(self, chat_id) -> dict:
        with self._state_lock:
            now = time.monotonic()
            self.sessions = {key: value for key, value in self.sessions.items() if now - value["seen"] < 1800}
            if len(self.sessions) >= 1000 and chat_id not in self.sessions:
                self.sessions.pop(next(iter(self.sessions)))
            session = self.sessions.setdefault(chat_id, {})
            session["seen"] = now
            return session

    def cancel_request(self, chat_id: int) -> None:
        with self._state_lock:
            pending = self.inflight.get(chat_id)
            if pending:
                pending.set()

    def dispatch_message(self, message: dict) -> None:
        """Keep polling responsive while at most two chats wait on n8n/OCR."""
        chat_id = message["chat"]["id"]
        text = message.get("text") or ""
        command = text.split(" ", 1)[0].split("@")[0].removeprefix("/")
        if text.startswith("/") and command not in PROCEDURES:
            self.handle_message(message)
            return
        skey = self.session_key(message)
        with self._state_lock:
            if skey in self.inflight or len(self.inflight) >= 2:
                lang = self.session(skey).get("language", "fr")
                self.safe_send(chat_id, BUSY[lang], navigation(lang))
                return
            cancelled = threading.Event()
            self.inflight[skey] = cancelled

        def work():
            try:
                self.handle_message(message, cancelled)
            finally:
                with self._state_lock:
                    if self.inflight.get(skey) is cancelled:
                        self.inflight.pop(skey, None)
        # A blocked upstream call cannot prevent process shutdown. No uploads are stored on disk.
        threading.Thread(target=work, daemon=True).start()

    def safe_send(self, chat_id: int, text: str, reply_markup=None) -> None:
        try:
            self.send_text(chat_id, text, reply_markup)
        except Exception as exc:
            log.warning("telegram_send_failed", extra={"fields": {"error": type(exc).__name__}})

    # ------------------------------------------------------------------ Telegram API
    def api(self, method: str, http_timeout=httpx.USE_CLIENT_DEFAULT, **params) -> dict:
        for attempt in range(3):
            try:
                resp = self.client.post(f"{self._base}/{method}", json=params, timeout=http_timeout)
                try:
                    data = resp.json()
                except ValueError:
                    data = {}
                code = data.get("error_code", resp.status_code)
                if code == 409:
                    raise PollingConflict("Another polling instance is running")
                if code == 429 or resp.status_code >= 500:
                    delay = max(2 ** attempt, float((data.get("parameters") or {}).get("retry_after", 0)))
                    if attempt < 2:
                        self.stop.wait(delay)
                        continue
                if resp.status_code >= 400:
                    raise TelegramAPIError(f"Telegram API failed (HTTP {resp.status_code})")
                if not data.get("ok"):
                    raise RuntimeError("Telegram API rejected request")
                return data["result"]
            except (httpx.TimeoutException, httpx.NetworkError):
                # Sending may have succeeded: do not duplicate replies after an ambiguous timeout.
                if method == "sendMessage" or attempt == 2:
                    raise TelegramAPIError("Telegram API network failure") from None
                self.stop.wait(2 ** attempt)
        raise RuntimeError("Telegram API unavailable")

    def download_file(self, file_id: str) -> bytes:
        info = self.api("getFile", file_id=file_id)
        size = info.get("file_size") or 0
        if size > self.max_upload_bytes:
            raise ValueError("file too large")
        path = info["file_path"]
        if path.startswith("/") or ".." in path.split("/") or ":" in path:
            raise ValueError("Invalid download path")
        data = bytearray()
        try:
            with self.client.stream("GET", f"{self._file_base}/{path}", timeout=120) as resp:
                if resp.status_code >= 400:
                    raise TelegramAPIError(f"Telegram download failed (HTTP {resp.status_code})")
                for chunk in resp.iter_bytes(65536):
                    data.extend(chunk)
                    if len(data) > self.max_upload_bytes:
                        raise ValueError("file too large")
        except httpx.HTTPError:
            raise TelegramAPIError("Telegram download network failure") from None
        return bytes(data)

    def send_text(self, chat_id: int, text: str, reply_markup=None) -> None:
        parts = split_message(text)
        for index, part in enumerate(parts):
            self.api("sendMessage", chat_id=chat_id, text=part, disable_web_page_preview=True,
                     **({"reply_markup": reply_markup} if reply_markup and index == len(parts) - 1 else {}))

    # ------------------------------------------------------------------ message handling
    def build_payload(self, message: dict) -> dict | None:
        """Translates a Telegram message into the n8n assistant webhook payload."""
        user_lang = TELEGRAM_LANGUAGES.get(((message.get("from") or {}).get("language_code") or "")[:2])
        if message.get("text"):
            text = message["text"].strip()
            payload = {"text": text}
            return payload
        file_id, mime, name = None, None, "upload"
        if message.get("photo"):
            photo = max(message["photo"], key=lambda p: p.get("file_size") or p.get("width", 0))
            file_id, mime, name = photo["file_id"], "image/jpeg", "photo.jpg"
        elif message.get("document"):
            doc = message["document"]
            if doc.get("mime_type") in SUPPORTED_DOCUMENT_TYPES:
                file_id, mime, name = doc["file_id"], doc["mime_type"], doc.get("file_name") or "upload"
        if file_id is None:
            return None
        attachment = message.get("document") or max(message.get("photo") or [{}], key=lambda p: p.get("file_size", 0))
        if attachment.get("file_size", 0) > self.max_upload_bytes:
            raise ValueError("file too large")
        data = self.download_file(file_id)
        valid = ((mime == "application/pdf" and data.startswith(b"%PDF-")) or
                 (mime == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n")) or
                 (mime == "image/jpeg" and data.startswith(b"\xff\xd8\xff")))
        if not valid:
            raise ValueError("Invalid file signature")
        name = Path(name.replace("\\", "/")).name[:255]
        payload = {"file": {"filename": name, "mime_type": mime, "data_b64": base64.b64encode(data).decode()}}
        del data
        caption = message.get("caption")
        if caption:
            payload["caption"] = caption[:1000]
        elif user_lang:
            payload["language"] = user_lang
        return payload

    def handle_message(self, message: dict, cancelled: threading.Event | None = None) -> None:
        chat_id = message["chat"]["id"]
        if self.stop.is_set() or (cancelled and cancelled.is_set()):
            return
        user_lang = TELEGRAM_LANGUAGES.get(((message.get("from") or {}).get("language_code") or "")[:2], "fr")
        skey = self.session_key(message)
        session = self.session(skey)
        user_lang = session.get("language", user_lang)
        command = (message.get("text") or "").split(" ", 1)[0].split("@")[0]
        if command.startswith("/"):
            command = command[1:]
            if command in PROCEDURES:
                session.pop("checklist", None)
                session["procedure"] = PROCEDURES[command]
                message = {**message, "text": "Required documents for " + PROCEDURES[command]}
            else:
                key = {"start": "welcome", "procedures": "choose", "form_check": "form"}.get(command, command)
                if command == "dossier_check":
                    session["upload_mode"] = "dossier"
                elif command == "form_check":
                    session.pop("upload_mode", None)
                if command == "cancel":
                    self.cancel_request(skey)
                    with self._state_lock:
                        self.sessions.pop(skey, None)
                if key not in TEXT[user_lang]:
                    key = "help"
                if command in {"procedures", "checklist"}:
                    session.pop("procedure", None)
                    session["checklist"] = command == "checklist"
                markup = (language_keyboard(user_lang) if command == "language" else
                          main_keyboard(user_lang) if command == "start" else
                          keyboard(user_lang) if command in {"procedures", "checklist"} else navigation(user_lang))
                self.safe_send(chat_id, TEXT[user_lang][key].format(mb=self.max_upload_bytes // 1048576), markup)
                return
        upload_mode = session.get("upload_mode")
        started = time.perf_counter()
        stop_typing = threading.Event()
        typing = threading.Thread(target=self._keep_typing, args=(chat_id, stop_typing, cancelled), daemon=True)
        typing.start()
        kind = "text" if message.get("text") else "file"
        try:
            try:
                payload = self.build_payload(message)
            except ValueError:
                payload = None
            if payload is None:
                mb = str(self.max_upload_bytes // (1024 * 1024))
                self.send_text(chat_id, UNSUPPORTED_TEXT.get(user_lang, UNSUPPORTED_TEXT["ar"]).format(mb=mb))
                return
            if payload.get("file") and upload_mode == "dossier":
                payload["mode"] = "dossier"
            if command in PROCEDURES:
                payload["language"] = user_lang
            elif session.get("language"):
                payload["language"] = session["language"]
            if payload.get("text"):
                if self.dialogue_enabled:
                    context = dict(session.get("dialogue") or {})
                    if command in PROCEDURES:
                        context = {"category": PROCEDURES[command].replace(" ","_")}
                    payload["context"] = context
                if len(payload["text"]) > 2000:
                    self.send_text(chat_id, TEXT[user_lang]["long"], navigation(user_lang))
                    return
                if session.pop("checklist", False):
                    prefix = "Required documents: "
                    if len(payload["text"]) + len(prefix) <= 2000:
                        payload["text"] = prefix + payload["text"]
                if not self.dialogue_enabled and session.get("procedure") and command not in PROCEDURES:
                    # Context is explicitly selected through a menu/command, never inferred here.
                    suffix = "\nProcedure context: " + session["procedure"]
                    if len(payload["text"]) + len(suffix) <= 2000:
                        payload["text"] += suffix
            payload = AssistantRequest.model_validate(payload).model_dump(exclude_none=True)
            for attempt in range(3):
                if self.stop.is_set() or (cancelled and cancelled.is_set()):
                    return
                try:
                    resp = self.client.post(self.webhook_url, json=payload, timeout=self.webhook_timeout)
                    resp.raise_for_status()
                    break
                except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                    if attempt == 2 or (isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500):
                        raise
                    self.stop.wait(2 ** attempt)
            if self.stop.is_set() or (cancelled and cancelled.is_set()):
                return
            result = AssistantResponse.model_validate(resp.json())
            # Retain only validated routing metadata, never the user's question or document values.
            category = result.route.get("procedure_category")
            if payload.get("text") and category in {
                "passport", "national_id", "business_registration", "birth_certificate"
            }:
                with self._state_lock:
                    # A cancelled or expired interaction must not restore a cleared session.
                    if self.sessions.get(skey) is session and not (cancelled and cancelled.is_set()):
                        session["procedure"] = category.replace("_", " ")
            if self.dialogue_enabled and result.context is not None and payload.get("text"):
                with self._state_lock:
                    if self.sessions.get(skey) is session and not (cancelled and cancelled.is_set()):
                        session["dialogue"] = result.context.model_dump(exclude_none=True)
            detected = result.language or result.route.get("language")
            if not session.get("language") and detected in TEXT:
                user_lang = detected
            text = result.text
            if result.agent == "dossier_validator":
                text = render_dossier(result, user_lang)
            if result.agent == "form_helper":
                if result.error:
                    text += "\n\n" + TEXT[user_lang]["unreadable"]
                elif result.recognised is False:
                    text += "\n\n" + TEXT[user_lang]["unsupported_form"]
                elif result.recognised is True:
                    status = "missing_fields" if result.missing else "no_missing"
                    text += "\n\n" + TEXT[user_lang][status].format(count=len(result.missing))
                text += "\n\n" + TEXT[user_lang]["manual"]
                if result.form_url and result.form_url.startswith("https://") and result.form_url not in text:
                    text += "\n" + result.form_url
            for warning in result.warnings:
                if warning not in text:
                    text += "\n\n" + warning
            for citation in result.citations:
                url = citation.get("url") or citation.get("source_url")
                if isinstance(url, str) and url.startswith("https://") and url not in text:
                    text += "\n" + url
            if result.error and result.agent not in {"form_helper", "dossier_validator"}:
                text += "\n" + ERROR_TEXT.get(user_lang, ERROR_TEXT["ar"])
            if cancelled and cancelled.is_set():
                return
            self.send_text(chat_id, text, navigation(user_lang))
            log.info("telegram_message_answered", extra={"fields": {
                "kind": kind, "ms": round((time.perf_counter() - started) * 1000),
                "agent": (resp.json() or {}).get("agent")}})
        except Exception as exc:  # never let one message stop the bridge
            if self.stop.is_set() or (cancelled and cancelled.is_set()):
                return
            log.warning("telegram_message_failed", extra={"fields": {"kind": kind, "error": type(exc).__name__}})
            try:
                self.send_text(chat_id, ERROR_TEXT.get(user_lang, ERROR_TEXT["ar"]))
            except Exception as send_exc:
                log.warning("telegram_send_failed", extra={"fields": {"error": type(send_exc).__name__}})
        finally:
            stop_typing.set()

    def _keep_typing(self, chat_id: int, stop: threading.Event, cancelled=None) -> None:
        while not stop.is_set() and not self.stop.is_set() and not (cancelled and cancelled.is_set()):
            try:
                self.api("sendChatAction", chat_id=chat_id, action="typing", http_timeout=10)
            except Exception:
                pass
            stop.wait(4.5)

    # ------------------------------------------------------------------ polling loop
    def poll_once(self) -> list[dict]:
        params = {"timeout": POLL_TIMEOUT_SECONDS, "allowed_updates": ["message", "callback_query"]}
        if self.offset is not None:
            params["offset"] = self.offset
        updates = self.api("getUpdates", http_timeout=POLL_TIMEOUT_SECONDS + 10, **params)
        messages = []
        for update in sorted(updates, key=lambda u: u["update_id"]):
            if self.offset is not None and update["update_id"] < self.offset:
                continue
            self.offset = update["update_id"] + 1
            if "callback_query" in update:
                callback = update["callback_query"]
                self.api("answerCallbackQuery", callback_query_id=callback["id"])
                msg = callback.get("message")
                if not msg:
                    continue
                action, _, value = callback.get("data", "").partition(":")
                chat_id = msg["chat"]["id"]
                skey = self.session_key(msg, callback.get("from", {}))
                session = self.session(skey)
                lang = session.get("language", TELEGRAM_LANGUAGES.get(
                    (callback.get("from", {}).get("language_code") or "")[:2], "fr"))
                if action == "language" and value in TEXT:
                    session["language"] = value
                    self.safe_send(chat_id, TEXT[value]["selected"], keyboard(value))
                elif action == "procedure" and value in PROCEDURES:
                    messages.append({**msg, "from": callback.get("from", {}), "text": "/" + value})
                elif action == "menu":
                    if value == "main":
                        self.safe_send(chat_id, TEXT[lang]["welcome"], main_keyboard(lang))
                    elif value == "new":
                        self.cancel_request(skey)
                        session.pop("procedure", None)
                        session.pop("checklist", None)
                        session.pop("upload_mode", None)
                        session.pop("dialogue", None)
                        self.safe_send(chat_id, TEXT[lang]["ask"], navigation(lang))
                    elif value in {"procedures", "language", "form_check", "dossier_check"}:
                        messages.append({**msg, "from": callback.get("from", {}), "text": "/" + value})
            elif "message" in update:
                messages.append(update["message"])
        self.last_poll = time.monotonic()
        Path("/tmp/telegram-bridge-health").touch() if Path("/tmp").exists() else None
        return messages

    def run_forever(self) -> None:
        # A bound local socket provides a process lock on both Windows and Linux.
        import socket
        lock = socket.socket()
        try:
            lock.bind(("127.0.0.1", 47639))
            self.api("getMe")
            self.api("setMyCommands", commands=[{"command": c, "description": c.replace("_", " ").capitalize()} for c in COMMANDS])
            self.api("deleteWebhook", drop_pending_updates=False)
            log.info("telegram_bridge_started")
            backoff = 1.0
            while not self.stop.is_set():
                try:
                    # One active request per chat and two globally bound uploads and model work.
                    for message in self.poll_once():
                        if self.stop.is_set():
                            break
                        self.dispatch_message(message)
                    backoff = 1.0
                except PollingConflict:
                    raise
                except Exception as exc:
                    log.warning("telegram_poll_failed", extra={"fields": {"error": type(exc).__name__}})
                    self.stop.wait(backoff)
                    backoff = min(backoff * 2, 60)
        finally:
            self.stop.set()
            with self._state_lock:
                for pending in self.inflight.values():
                    pending.set()
            lock.close()
            self.client.close()
            self.sessions.clear()


class PollingConflict(RuntimeError):
    """Telegram detected a competing poller; exit instead of competing."""


class TelegramAPIError(RuntimeError):
    """Safe error without Telegram URLs, credentials or response bodies."""
