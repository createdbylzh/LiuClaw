from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

ReasoningLevel = Literal["low", "medium", "high"]
StreamEventType = Literal[
    "start",
    "text_start",
    "text_delta",
    "text_end",
    "thinking_start",
    "thinking_delta",
    "thinking_end",
    "toolcall_start",
    "toolcall_delta",
    "toolcall_end",
    "done",
    "error",
]


@dataclass(slots=True)
class Tool:
    """定义可供模型调用的工具。"""

    name: str
    description: str | None = None
    inputSchema: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolCall:
    """表示 assistant 发起的一次工具调用。"""

    id: str
    name: str
    arguments: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class UserMessage:
    """表示用户输入消息。"""

    role: Literal["user"] = "user"
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AssistantMessage:
    """表示 assistant 消息，也是 `complete()` 的最终结果对象。"""

    role: Literal["assistant"] = "assistant"
    content: str = ""
    thinking: str = ""
    toolCalls: list[ToolCall] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """返回 assistant 的最终文本内容。"""

        return self.content


@dataclass(slots=True)
class ToolResultMessage:
    """表示工具执行结果消息，供上层回填给模型。"""

    role: Literal["tool"] = "tool"
    toolCallId: str = ""
    toolName: str = ""
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


ConversationMessage: TypeAlias = UserMessage | AssistantMessage | ToolResultMessage


@dataclass(slots=True)
class Model:
    """描述一个可供统一接入层使用的模型元数据。"""

    id: str
    provider: str
    inputPrice: float
    outputPrice: float
    contextWindow: int
    maxOutputTokens: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Context:
    """描述一次模型调用的统一上下文。"""

    systemPrompt: str | None = None
    messages: list[ConversationMessage] = field(default_factory=list)
    tools: list[Tool] = field(default_factory=list)


@dataclass(slots=True)
class StreamEvent:
    """定义统一流式事件对象。"""

    type: StreamEventType
    model: Model | None = None
    provider: str | None = None
    text: str | None = None
    thinking: str | None = None
    toolCallId: str | None = None
    toolName: str | None = None
    argumentsDelta: str | None = None
    arguments: str | None = None
    assistantMessage: AssistantMessage | None = None
    usage: dict[str, Any] | None = None
    stopReason: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    rawEvent: Any | None = None



def ensure_message(value: ConversationMessage | dict[str, Any]) -> ConversationMessage:
    """将输入值规范化为新的消息类型。"""

    if isinstance(value, (UserMessage, AssistantMessage, ToolResultMessage)):
        return value
    if not isinstance(value, dict):
        raise TypeError("messages entries must be a message object or dict")

    role = value.get("role")
    if role == "user":
        return UserMessage(
            content=str(value.get("content", "")),
            metadata=dict(value.get("metadata", {})),
        )
    if role == "assistant":
        tool_calls = [ensure_tool_call(item) for item in value.get("toolCalls", [])]
        return AssistantMessage(
            content=str(value.get("content", "")),
            thinking=str(value.get("thinking", "")),
            toolCalls=tool_calls,
            metadata=dict(value.get("metadata", {})),
        )
    if role == "tool":
        return ToolResultMessage(
            toolCallId=str(value.get("toolCallId", "")),
            toolName=str(value.get("toolName", "")),
            content=str(value.get("content", "")),
            metadata=dict(value.get("metadata", {})),
        )
    raise ValueError("message role must be one of: user, assistant, tool")



def ensure_tool(value: Tool | dict[str, Any]) -> Tool:
    """将输入值规范化为工具定义。"""

    if isinstance(value, Tool):
        return value
    if not isinstance(value, dict):
        raise TypeError("tools entries must be Tool or dict")
    return Tool(
        name=str(value.get("name", "")),
        description=value.get("description"),
        inputSchema=dict(value.get("inputSchema", value.get("input_schema", {}))),
        metadata=dict(value.get("metadata", {})),
    )



def ensure_tool_call(value: ToolCall | dict[str, Any]) -> ToolCall:
    """将输入值规范化为工具调用对象。"""

    if isinstance(value, ToolCall):
        return value
    if not isinstance(value, dict):
        raise TypeError("toolCalls entries must be ToolCall or dict")
    return ToolCall(
        id=str(value.get("id", "")),
        name=str(value.get("name", "")),
        arguments=str(value.get("arguments", "")),
        metadata=dict(value.get("metadata", {})),
    )



def ensure_context(value: Context | dict[str, Any]) -> Context:
    """将输入值规范化为统一的 Context 对象。"""

    if isinstance(value, Context):
        return value
    if not isinstance(value, dict):
        raise TypeError("context must be Context or dict")
    return Context(
        systemPrompt=value.get("systemPrompt"),
        messages=[ensure_message(item) for item in value.get("messages", [])],
        tools=[ensure_tool(item) for item in value.get("tools", [])],
    )



def ensure_model(value: Model | str) -> Model:
    """将模型对象或模型 ID 规范化为 `Model`。"""

    if isinstance(value, Model):
        return value
    if not isinstance(value, str):
        raise TypeError("model must be a Model or model id string")
    from .models import get_model

    return get_model(value)
