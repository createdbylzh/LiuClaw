from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeAlias

from ai.registry import ProviderRegistry
from ai.session import StreamSession
from ai.types import (
    AssistantMessage,
    ConversationMessage,
    Model,
    ReasoningLevel,
    Tool,
    ToolCall,
    ToolResultMessage,
)

AgentEventType: TypeAlias = Literal[
    "agent_start",
    "agent_end",
    "turn_start",
    "turn_end",
    "message_start",
    "message_update",
    "message_end",
    "tool_execution_start",
    "tool_execution_update",
    "tool_execution_end",
]
ToolExecutionMode: TypeAlias = Literal["serial", "parallel"]
ToolExecutionResult: TypeAlias = str | dict[str, Any] | ToolResultMessage


@dataclass(slots=True)
class AgentContext:
    """定义一次 Agent 调用 AI 或工具时使用的上下文快照。"""

    systemPrompt: str | None = None
    history: list[ConversationMessage] = field(default_factory=list)
    tools: list[Tool] = field(default_factory=list)


class AgentStreamFn(Protocol):
    """定义“调用 AI 的函数”应遵循的统一签名。"""

    async def __call__(
        self,
        model: Model | str,
        context: AgentContext,
        thinking: ReasoningLevel | None,
        registry: ProviderRegistry | None = None,
    ) -> StreamSession:
        """根据模型、上下文和思考级别返回一个流式会话。"""


class AgentToolExecutor(Protocol):
    """定义 Agent 工具执行函数的统一签名。"""

    def __call__(
        self,
        arguments: str,
        context: AgentContext,
    ) -> Awaitable[ToolExecutionResult] | ToolExecutionResult:
        """执行工具，并返回工具结果。"""


@dataclass(slots=True)
class AgentTool(Tool):
    """定义可供 Agent 调用的工具。"""

    execute: AgentToolExecutor | None = None


@dataclass(slots=True)
class AgentState:
    """定义 Agent 在循环运行中的实时状态。"""

    systemPrompt: str | None = None
    model: Model | str | None = None
    thinking: ReasoningLevel | None = None
    tools: list[AgentTool] = field(default_factory=list)
    history: list[ConversationMessage] = field(default_factory=list)
    isStreaming: bool = False
    currentMessage: AssistantMessage | None = None
    runningToolCall: ToolCall | None = None
    error: str | None = None


@dataclass(slots=True)
class BeforeToolCallContext:
    """定义 beforeToolCall 收到的上下文信息。"""

    state: AgentState
    tool: AgentTool
    toolCall: ToolCall
    arguments: str
    agentContext: AgentContext


@dataclass(slots=True)
class AfterToolCallContext:
    """定义 afterToolCall 收到的上下文信息。"""

    state: AgentState
    tool: AgentTool
    toolCall: ToolCall
    arguments: str
    result: ToolResultMessage
    agentContext: AgentContext


@dataclass(slots=True)
class BeforeToolCallAllow:
    """表示 beforeToolCall 允许工具继续执行。"""

    action: Literal["allow"] = "allow"


@dataclass(slots=True)
class BeforeToolCallSkip:
    """表示 beforeToolCall 跳过真实执行并直接返回替代结果。"""

    result: ToolExecutionResult
    action: Literal["skip"] = "skip"


@dataclass(slots=True)
class BeforeToolCallError:
    """表示 beforeToolCall 阻止工具执行并返回错误。"""

    error: str
    action: Literal["error"] = "error"


BeforeToolCallResult: TypeAlias = BeforeToolCallAllow | BeforeToolCallSkip | BeforeToolCallError | None


@dataclass(slots=True)
class AfterToolCallPass:
    """表示 afterToolCall 保留原始工具结果。"""

    action: Literal["pass"] = "pass"


@dataclass(slots=True)
class AfterToolCallReplace:
    """表示 afterToolCall 用新结果替换原始工具结果。"""

    result: ToolExecutionResult
    action: Literal["replace"] = "replace"


AfterToolCallResult: TypeAlias = AfterToolCallPass | AfterToolCallReplace | None


class BeforeToolCallFn(Protocol):
    """定义工具执行前安检钩子的签名。"""

    def __call__(
        self,
        context: BeforeToolCallContext,
    ) -> Awaitable[BeforeToolCallResult] | BeforeToolCallResult:
        """在工具执行前决定允许、跳过或阻止调用。"""


class AfterToolCallFn(Protocol):
    """定义工具执行后质检钩子的签名。"""

    def __call__(
        self,
        context: AfterToolCallContext,
    ) -> Awaitable[AfterToolCallResult] | AfterToolCallResult:
        """在工具执行后决定保留或替换结果。"""


class SteeringFn(Protocol):
    """定义中途插话消息获取函数的签名。"""

    def __call__(
        self,
        state: AgentState,
    ) -> Awaitable[list[ConversationMessage]] | list[ConversationMessage] | None:
        """在 turn 结束后获取 steering 消息。"""


class FollowUpFn(Protocol):
    """定义任务结束后 follow-up 消息获取函数的签名。"""

    def __call__(
        self,
        state: AgentState,
    ) -> Awaitable[list[ConversationMessage]] | list[ConversationMessage] | None:
        """在内层循环退出后获取 follow-up 消息。"""


@dataclass(slots=True)
class AgentLoopConfig:
    """定义 Agent 主循环运行所需的一切配置。"""

    systemPrompt: str | None = None
    model: Model | str | None = None
    thinking: ReasoningLevel | None = None
    tools: list[AgentTool] = field(default_factory=list)
    stream: AgentStreamFn | None = None
    steer: SteeringFn | None = None
    followUp: FollowUpFn | None = None
    toolExecutionMode: ToolExecutionMode = "serial"
    beforeToolCall: BeforeToolCallFn | None = None
    afterToolCall: AfterToolCallFn | None = None
    registry: ProviderRegistry | None = None


@dataclass(slots=True)
class AgentEvent:
    """定义对外暴露的统一 Agent 事件对象。"""

    type: AgentEventType
    state: AgentState | None = None
    message: ConversationMessage | AssistantMessage | ToolResultMessage | None = None
    messageDelta: str | None = None
    toolCall: ToolCall | None = None
    toolResult: ToolResultMessage | None = None
    error: str | None = None
