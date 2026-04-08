from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal


def utc_now_iso() -> str:
    """返回当前 UTC 时间的 ISO 8601 字符串。"""
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ChatAttachment:
    """聊天消息中的附件信息。"""

    original_name: str
    local_path: str = ""
    mime_type: str | None = None
    file_key: str | None = None
    message_id: str | None = None
    size: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChatEvent:
    """统一后的聊天事件模型，作为 mom 内部的核心输入。"""

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
    """聊天参与者信息。"""

    id: str
    name: str
    display_name: str | None = None


@dataclass(slots=True)
class ChatInfo:
    """聊天会话的基础信息。"""

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
    """runner 与外部聊天平台之间的交互抽象。"""

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
    """一次 Agent 执行结束后的汇总结果。"""

    stop_reason: Literal["completed", "aborted", "error"] = "completed"
    error_message: str | None = None
    main_message_id: str | None = None
    final_text: str = ""
    detail_count: int = 0
    suppressed_events_count: int = 0


@dataclass(slots=True)
class MomRenderConfig:
    """mom 输出渲染策略配置。"""

    render_mode: Literal["final_only", "streaming"] = "final_only"
    placeholder_text: str = "处理中…"
    show_intermediate_updates: bool = False
    show_tool_details: bool = False
    show_thinking: bool = False


@dataclass(slots=True)
class SessionRef:
    """频道与 Agent 会话之间的持久化引用。"""

    session_id: str
    branch_id: str = "main"
    synced_message_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ChannelState:
    """频道级运行态，记录是否忙碌、排队消息和停止状态。"""

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
    """写入频道日志文件的标准消息结构。"""

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
    """mom 在工作区下使用的目录与文件路径集合。"""

    workspace_root: Path
    root: Path
    channels_dir: Path
    events_dir: Path
    sessions_dir: Path
    settings_file: Path
    channel_index_file: Path

    def ensure_exists(self) -> None:
        """确保 mom 运行依赖的目录和配置文件已经存在。"""
        self.root.mkdir(parents=True, exist_ok=True)
        self.channels_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        if not self.settings_file.exists():
            self.settings_file.write_text("{}\n", encoding="utf-8")
        if not self.channel_index_file.exists():
            self.channel_index_file.write_text("{}\n", encoding="utf-8")
