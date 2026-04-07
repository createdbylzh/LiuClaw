from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ...core.agent_session import AgentSession
from ...core.types import SessionEvent


@dataclass(slots=True)
class MessageCard:
    """表示主输出区中的一张消息卡片。"""

    id: str
    title: str
    body: str = ""
    style: str = "assistant"


@dataclass(slots=True)
class ToolCard:
    """表示工具执行区中的一张工具卡片。"""

    id: str
    tool_name: str
    status: str
    arguments: str = ""
    output_preview: str = ""


@dataclass(slots=True)
class InteractiveState:
    """保存交互界面的全部可见状态。"""

    session_id: str
    model_id: str
    thinking: str | None
    cwd: Path
    theme: str
    submit_on_enter: bool = True
    is_running: bool = False
    last_error: str = ""
    status_message: str = ""
    current_tool: str = ""
    output_cards: list[MessageCard] = field(default_factory=list)
    thinking_cards: list[MessageCard] = field(default_factory=list)
    tool_cards: list[ToolCard] = field(default_factory=list)
    status_timeline: list[str] = field(default_factory=list)
    recent_sessions: list[dict] = field(default_factory=list)

    @classmethod
    def from_session(cls, session: AgentSession) -> "InteractiveState":
        """从当前会话对象构造界面初始状态。"""

        return cls(
            session_id=session.session_id,
            model_id=session.model.id,
            thinking=session.thinking,
            cwd=session.cwd,
            theme=session.settings.theme,
            recent_sessions=session.list_recent_sessions(),
        )

    def sync_from_session(self, session: AgentSession) -> None:
        """把会话对象中的最新信息同步到界面状态。"""

        self.session_id = session.session_id
        self.model_id = session.model.id
        self.thinking = session.thinking
        self.cwd = session.cwd
        self.theme = session.settings.theme
        self.recent_sessions = session.list_recent_sessions()

    def clear_output(self) -> None:
        """清空主输出区、思考区和工具区内容。"""

        self.output_cards.clear()
        self.thinking_cards.clear()
        self.tool_cards.clear()

    def add_status(self, message: str) -> None:
        """向状态时间线追加一条消息。"""

        self.status_message = message
        self.status_timeline.append(message)
        self.status_timeline = self.status_timeline[-20:]

    def apply_event(self, event: SessionEvent) -> None:
        """根据会话事件更新 UI 状态。"""

        if event.type == "message_start":
            self.output_cards.append(MessageCard(id=event.message_id or f"assistant-{len(self.output_cards)+1}", title="Assistant"))
            return
        if event.type == "message_delta":
            if not self.output_cards:
                self.output_cards.append(MessageCard(id=event.message_id or "assistant", title="Assistant"))
            self.output_cards[-1].body += event.delta
            return
        if event.type == "message_end":
            if not self.output_cards:
                self.output_cards.append(MessageCard(id=event.message_id or "assistant", title="Assistant"))
            self.output_cards[-1].body = event.message or self.output_cards[-1].body
            return
        if event.type == "thinking":
            self.thinking_cards.append(
                MessageCard(id=event.message_id or f"thinking-{len(self.thinking_cards)+1}", title="Thinking", body=event.message, style="thinking")
            )
            return
        if event.type == "status":
            self.add_status(event.message)
            return
        if event.type == "tool_start":
            self.current_tool = event.tool_name
            self.tool_cards.append(
                ToolCard(
                    id=event.message_id or f"tool-{len(self.tool_cards)+1}",
                    tool_name=event.tool_name,
                    status="running",
                    arguments=event.tool_arguments,
                )
            )
            self.add_status(f"工具开始: {event.tool_name}")
            return
        if event.type == "tool_update":
            self.current_tool = event.tool_name
            self.add_status(event.message)
            return
        if event.type == "tool_end":
            self.current_tool = ""
            if self.tool_cards:
                self.tool_cards[-1].status = "error" if event.status_level == "error" else "success"
                self.tool_cards[-1].output_preview = event.tool_output_preview or event.message
            self.add_status(f"工具完成: {event.tool_name}")
            return
        if event.type == "error":
            self.last_error = event.message
            self.add_status(event.message)

