from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ChatAttachment:
    original_name: str
    local_path: str = ""
    mime_type: str | None = None
    file_key: str | None = None
    message_id: str | None = None
    size: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChatEvent:
    platform: str
    chat_id: str
    message_id: str
    sender_id: str
    sender_name: str
    text: str
    attachments: list[ChatAttachment] = field(default_factory=list)
    is_direct: bool = False
    is_trigger: bool = False
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    chat_name: str | None = None
    mentions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChatUser:
    id: str
    name: str
    display_name: str | None = None


@dataclass(slots=True)
class ChatInfo:
    id: str
    name: str


RespondFn = Callable[[str, bool], Awaitable[str | None]]
ReplaceFn = Callable[[str], Awaitable[str | None]]
DetailFn = Callable[[str], Awaitable[str | None]]
UploadFn = Callable[[str, str | None], Awaitable[str | None]]
WorkingFn = Callable[[bool], Awaitable[None]]
DeleteFn = Callable[[], Awaitable[None]]


@dataclass(slots=True)
class ChatContext:
    message: ChatEvent
    chat_name: str | None
    users: list[ChatUser]
    chats: list[ChatInfo]
    respond: RespondFn
    replace_message: ReplaceFn
    respond_detail: DetailFn
    upload_file: UploadFn
    set_working: WorkingFn
    delete_message: DeleteFn
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RunResult:
    stop_reason: Literal["completed", "aborted", "error"] = "completed"
    error_message: str | None = None
    main_message_id: str | None = None
    final_text: str = ""
    detail_count: int = 0
    suppressed_events_count: int = 0


@dataclass(slots=True)
class MomRenderConfig:
    render_mode: Literal["final_only", "streaming"] = "final_only"
    placeholder_text: str = "处理中…"
    show_intermediate_updates: bool = False
    show_tool_details: bool = False
    show_thinking: bool = False


@dataclass(slots=True)
class SessionRef:
    session_id: str
    branch_id: str = "main"
    synced_message_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ChannelState:
    running: bool = False
    runner: Any | None = None
    store: Any | None = None
    stop_requested: bool = False
    stop_message_id: str | None = None
    queued_events: list[ChatEvent] = field(default_factory=list)
    current_message_id: str | None = None
    recent_incoming_message_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LoggedChatMessage:
    platform: str
    chat_id: str
    message_id: str
    sender_id: str
    sender_name: str
    text: str
    is_bot: bool
    created_at: str = field(default_factory=utc_now_iso)
    attachments: list[dict[str, Any]] = field(default_factory=list)
    direct: bool = False
    trigger: bool = False
    response_kind: str = "message"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MomPaths:
    workspace_root: Path
    root: Path
    channels_dir: Path
    events_dir: Path
    sessions_dir: Path
    settings_file: Path
    channel_index_file: Path

    def ensure_exists(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.channels_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        if not self.settings_file.exists():
            self.settings_file.write_text("{}\n", encoding="utf-8")
        if not self.channel_index_file.exists():
            self.channel_index_file.write_text("{}\n", encoding="utf-8")
