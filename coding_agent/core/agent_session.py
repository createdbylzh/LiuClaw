from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path

from ai.types import AssistantMessage, Context, ConversationMessage, Model, ToolResultMessage, UserMessage
from ai.utils.context_window import detect_context_overflow
from agent_core import (
    AfterToolCallContext,
    Agent,
    AgentEvent,
    AgentLoopConfig,
    AgentOptions,
    BeforeToolCallAllow,
    BeforeToolCallContext,
)

from .compaction import SessionCompactor, should_compact
from .resource_loader import ResourceLoader
from .session_manager import SessionManager
from .system_prompt import build_system_prompt
from .tools import build_default_tools, render_tools_markdown
from .types import CodingAgentSettings, ContextStats, SessionContext, SessionEvent


class AgentSession:
    """面向产品层的会话编排对象。"""

    def __init__(
        self,
        *,
        workspace_root: Path,
        cwd: Path,
        model: Model,
        thinking: str | None,
        settings: CodingAgentSettings,
        session_manager: SessionManager,
        resource_loader: ResourceLoader,
        session_id: str | None = None,
        branch_id: str = "main",
        stream_fn=None,
        registry=None,
    ) -> None:
        """初始化一次 coding-agent 会话运行时。"""

        self.workspace_root = workspace_root
        self.cwd = cwd
        self.model = model
        self.thinking = thinking
        self.settings = settings
        self.session_manager = session_manager
        self.resource_loader = resource_loader
        self.resources = resource_loader.load()
        self.tools = build_default_tools(self.workspace_root, settings)
        self.session_id = session_id
        self.branch_id = branch_id
        self.last_node_id: str | None = None
        self.compactor = SessionCompactor(session_manager, keep_turns=settings.compact_keep_turns)
        self._pending_steering_messages: list[ConversationMessage] = []
        self._pending_follow_up_messages: list[ConversationMessage] = []
        self._tool_activity_in_run = False
        self._follow_up_sent = False
        self._event_message_counter = 0
        self._current_assistant_message_id = ""
        self._agent = Agent(
            AgentOptions(
                loop=AgentLoopConfig(
                    model=model,
                    thinking=thinking,
                    systemPrompt=self._build_system_prompt(),
                    tools=self.tools,
                    stream=stream_fn,
                    steer=self._steer,
                    followUp=self._follow_up,
                    beforeToolCall=self._before_tool_call,
                    afterToolCall=self._after_tool_call,
                    registry=registry,
                )
            )
        )
        if self.session_id is None:
            snapshot = self.session_manager.create_session(cwd=cwd, model_id=model.id)
            self.session_id = snapshot.session_id
            self.branch_id = snapshot.branch_id

    def _build_system_prompt(self) -> str:
        """根据当前模型、目录、资源和工具构建系统提示。"""

        context = SessionContext(
            workspace_root=self.workspace_root,
            cwd=self.cwd,
            model=self.model,
            thinking=self.thinking,
            settings=self.settings,
            resources=self.resources,
            tools_markdown=render_tools_markdown(self.tools),
        )
        return build_system_prompt(context)

    def send_user_message(self, content: str) -> None:
        """接收用户输入，写入会话存储并加入待发送队列。"""

        message = UserMessage(content=content)
        self.session_manager.append_message(
            self.session_id,
            message=message,
            branch_id=self.branch_id,
            parent_id=self.last_node_id,
        )
        self.last_node_id = self.session_manager.load_session(self.session_id).nodes[-1].id
        self._agent.enqueue(message)

    def resume_session(self) -> None:
        """从持久化会话恢复历史上下文并同步到底层 Agent。"""

        history = self.session_manager.build_context_messages(self.session_id, self.branch_id)
        self._agent.setState(
            replace(
                self._agent.getState(),
                history=history,
                systemPrompt=self._build_system_prompt(),
                model=self.model,
                thinking=self.thinking,
                tools=self.tools,
            )
        )
        snapshot = self.session_manager.load_session(self.session_id)
        if snapshot.nodes:
            self.last_node_id = snapshot.nodes[-1].id

    def switch_model(self, model: Model) -> None:
        """切换当前会话使用的模型，并更新系统提示。"""

        self.model = model
        self._agent.setModel(model)
        self._agent.setSystemPrompt(self._build_system_prompt())
        meta = self.session_manager._read_meta(self.session_id)
        meta["model_id"] = model.id
        self.session_manager._write_meta(self.session_id, meta)

    def set_thinking(self, thinking: str | None) -> None:
        """调整当前会话的思考等级，并更新系统提示。"""

        self.thinking = thinking
        self._agent.setThinking(thinking)
        self._agent.setSystemPrompt(self._build_system_prompt())

    def compact(self):
        """手动触发当前会话分支的上下文压缩。"""

        return self.compactor.compact_session(self.session_id, self.branch_id)

    def cancel(self) -> None:
        """取消当前运行中的 agent 循环。"""

        self._agent.cancel()

    def list_recent_sessions(self, limit: int = 10) -> list[dict]:
        """列出当前工作区的最近会话。"""

        return self.session_manager.list_recent_sessions(limit=limit, cwd=self.cwd)

    def get_last_user_message(self) -> str | None:
        """返回当前会话最近一条真实用户输入。"""

        messages = self.session_manager.build_context_messages(self.session_id, self.branch_id)
        for message in reversed(messages):
            if isinstance(message, UserMessage) and not message.metadata.get("steering") and not message.metadata.get("follow_up"):
                return message.content
        return None

    async def run_turn(self) -> AsyncIterator[SessionEvent]:
        """运行一轮会话，并把底层事件映射为 UI 事件流。"""

        self._pending_steering_messages.clear()
        self._pending_follow_up_messages.clear()
        self._tool_activity_in_run = False
        self._follow_up_sent = False
        if not self._agent.pendingMessages and self._agent.state.history:
            session = await self._agent.continueConversation()
        else:
            self.resume_session()
            self._maybe_auto_compact()
            session = await self._agent.run()

        async for event in session.consume():
            for mapped in self._map_event(event):
                yield mapped
            if event.type == "message_end" and isinstance(event.message, UserMessage):
                self._persist_control_message(event.message)
            if event.type == "message_end" and isinstance(event.message, AssistantMessage):
                self._persist_assistant(event.message)
            if event.type == "tool_execution_end" and event.toolResult is not None:
                self._persist_tool_result(event.toolResult)

    def _persist_assistant(self, message: AssistantMessage) -> None:
        """把 assistant 消息持久化为会话节点。"""

        node = self.session_manager.append_message(
            self.session_id,
            message=message,
            branch_id=self.branch_id,
            parent_id=self.last_node_id,
        )
        self.last_node_id = node.id

    def _persist_tool_result(self, message: ToolResultMessage) -> None:
        """把工具结果消息持久化为会话节点。"""

        node = self.session_manager.append_message(
            self.session_id,
            message=message,
            branch_id=self.branch_id,
            parent_id=self.last_node_id,
        )
        self.last_node_id = node.id

    def _persist_control_message(self, message: UserMessage) -> None:
        """把 steering 或 follow-up 注入的控制消息持久化。"""

        if not (message.metadata.get("steering") or message.metadata.get("follow_up")):
            return
        node = self.session_manager.append_message(
            self.session_id,
            message=message,
            branch_id=self.branch_id,
            parent_id=self.last_node_id,
        )
        self.last_node_id = node.id

    def _map_event(self, event: AgentEvent) -> list[SessionEvent]:
        """把 `agent_core` 事件转换成交互层事件。"""

        events: list[SessionEvent] = []
        if event.type == "message_start":
            self._event_message_counter += 1
            self._current_assistant_message_id = f"assistant-{self._event_message_counter}"
            events.append(
                SessionEvent(
                    type="message_start",
                    message="",
                    panel="main",
                    message_id=self._current_assistant_message_id,
                )
            )
            return events
        if event.type == "message_update":
            events.append(
                SessionEvent(
                    type="message_delta",
                    delta=event.messageDelta or "",
                    panel="main",
                    is_transient=True,
                    message_id=self._current_assistant_message_id,
                )
            )
            return events
        if event.type == "message_end" and isinstance(event.message, UserMessage):
            if event.message.metadata.get("steering"):
                events.append(
                    SessionEvent(
                        type="status",
                        message=event.message.content,
                        panel="status",
                        status_level="info",
                        payload={"source": "steering"},
                    )
                )
                return events
            if event.message.metadata.get("follow_up"):
                events.append(
                    SessionEvent(
                        type="status",
                        message="正在基于工具结果继续整理最终答复",
                        panel="status",
                        status_level="info",
                        payload={"source": "follow_up"},
                    )
                )
                return events
        if event.type == "message_end" and isinstance(event.message, AssistantMessage):
            if event.message.thinking:
                events.append(
                    SessionEvent(
                        type="thinking",
                        message=event.message.thinking,
                        panel="thinking",
                        message_id=self._current_assistant_message_id,
                    )
                )
            events.append(
                SessionEvent(
                    type="message_end",
                    message=event.message.content,
                    panel="main",
                    message_id=self._current_assistant_message_id,
                )
            )
            return events
        if event.type == "tool_execution_start":
            events.append(
                SessionEvent(
                    type="tool_start",
                    tool_name=event.toolCall.name if event.toolCall else "",
                    panel="tool",
                    status_level="info",
                    tool_arguments=event.toolCall.arguments if event.toolCall else "",
                    message_id=event.toolCall.id if event.toolCall else "",
                )
            )
            return events
        if event.type == "tool_execution_update":
            name = event.toolCall.name if event.toolCall else ""
            events.append(
                SessionEvent(
                    type="tool_update",
                    tool_name=name,
                    message=f"running {name}",
                    panel="tool",
                    status_level="info",
                    is_transient=True,
                    tool_arguments=event.toolCall.arguments if event.toolCall else "",
                    message_id=event.toolCall.id if event.toolCall else "",
                )
            )
            return events
        if event.type == "tool_execution_end":
            tool_name = event.toolResult.toolName if event.toolResult else ""
            tool_message = event.toolResult.content if event.toolResult else ""
            events.append(
                SessionEvent(
                    type="tool_end",
                    tool_name=tool_name,
                    message=tool_message,
                    panel="tool",
                    status_level="error" if event.error else "success",
                    tool_output_preview=tool_message[:300],
                    message_id=event.toolResult.toolCallId if event.toolResult else "",
                )
            )
            return events
        if event.type == "agent_end" and event.error:
            events.append(
                SessionEvent(
                    type="error",
                    error=event.error,
                    message=event.error,
                    panel="error",
                    status_level="error",
                )
            )
            return events
        return events

    def _maybe_auto_compact(self) -> None:
        """在发送请求前根据上下文大小决定是否自动压缩。"""

        if not self.settings.auto_compact:
            return
        messages = self.session_manager.build_context_messages(self.session_id, self.branch_id)
        context = Context(systemPrompt=self._build_system_prompt(), messages=messages, tools=self.tools)
        report = detect_context_overflow(self.model, context)
        ratio = report.total_tokens / report.limit if report.limit else 0.0
        stats = ContextStats(estimated_tokens=report.total_tokens, limit=report.limit, ratio=ratio)
        if should_compact(stats, self.settings, self.model):
            self.compact()

    async def _steer(self, state) -> list[ConversationMessage]:
        """在工具执行轮次之间注入 steering 控制消息。"""

        if not self._pending_steering_messages:
            return []
        messages = [replace(message) for message in self._pending_steering_messages]
        self._pending_steering_messages.clear()
        return messages

    async def _follow_up(self, state) -> list[ConversationMessage]:
        """在 AI 暂时完成工作后注入 follow-up 控制消息。"""

        if self._pending_follow_up_messages:
            messages = [replace(message) for message in self._pending_follow_up_messages]
            self._pending_follow_up_messages.clear()
            self._follow_up_sent = True
            return messages
        if not self._tool_activity_in_run or self._follow_up_sent:
            return []
        last_message = state.history[-1] if state.history else None
        if not isinstance(last_message, AssistantMessage) or last_message.toolCalls:
            return []
        self._follow_up_sent = True
        return [
            UserMessage(
                content="请基于当前工具执行结果给出最终答复；如果任务尚未完成，请继续推进并明确下一步。",
                metadata={"follow_up": True},
            )
        ]

    async def _before_tool_call(self, context: BeforeToolCallContext):
        """在工具调用前排入 steering 消息。"""

        self._tool_activity_in_run = True
        self._pending_steering_messages.append(
            UserMessage(
                content=f"[Steering] 即将执行工具 `{context.toolCall.name}`，参数如下：\n{context.arguments}",
                metadata={"steering": True, "phase": "before_tool", "tool_name": context.toolCall.name},
            )
        )
        return BeforeToolCallAllow()

    async def _after_tool_call(self, context: AfterToolCallContext):
        """在工具调用后排入 steering 消息，并为最终总结启用 follow-up。"""

        self._tool_activity_in_run = True
        self._pending_steering_messages.append(
            UserMessage(
                content=f"[Steering] 工具 `{context.toolCall.name}` 已执行完成，请结合工具结果继续工作。",
                metadata={"steering": True, "phase": "after_tool", "tool_name": context.toolCall.name},
            )
        )
        return None
