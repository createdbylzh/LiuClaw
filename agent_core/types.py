from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from typing import Any, Literal, Protocol, TypeAlias

from ai.registry import ProviderRegistry
from ai.session import StreamSession
from ai.types import (
    AssistantMessage,
    Context,
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
AgentErrorKind: TypeAlias = Literal["provider_error", "tool_error", "runtime_error", "aborted"]
ToolExecutionResult: TypeAlias = str | dict[str, Any] | ToolResultMessage
AgentPayload: TypeAlias = dict[str, Any]


@dataclass(slots=True)
class AbortSignal:
    """定义 Agent 内统一使用的中断信号。"""

    reason: str | None = None
    _event: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def aborted(self) -> bool:
        """返回当前信号是否已被中断。"""

        return self._event.is_set()

    def abort(self, reason: str | None = None) -> None:
        """触发中断并记录可选原因。"""

        if reason is not None:
            self.reason = reason
        self._event.set()

    async def wait(self) -> None:
        """等待直到信号进入中断状态。"""

        await self._event.wait()

    def throw_if_aborted(self) -> None:
        """在已中断时抛出取消异常。"""

        if self.aborted:
            raise asyncio.CancelledError(self.reason or "aborted")


@dataclass(slots=True)
class AgentError:
    """定义 Agent 运行期统一错误对象。"""

    kind: AgentErrorKind
    message: str
    details: Any | None = None
    retriable: bool = False

    def __str__(self) -> str:
        return self.message

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.message == other
        if not isinstance(other, AgentError):
            return False
        return (
            self.kind == other.kind
            and self.message == other.message
            and self.details == other.details
            and self.retriable == other.retriable
        )


@dataclass(slots=True)
class AgentRuntimeFlags:
    """定义 Agent 运行中的临时标记位。"""

    isStreaming: bool = False
    isRunning: bool = False
    isCancelled: bool = False
    turnIndex: int = 0
    retryCount: int = 0


@dataclass(slots=True)
class AgentContext:
    """定义一次 Agent 调用 AI 或工具时使用的上下文快照。"""

    systemPrompt: str | None = None
    messages: list[Any] = field(default_factory=list)
    tools: list[Tool] = field(default_factory=list)

    @property
    def history(self) -> list[Any]:
        """兼容旧实现读取 history。"""

        return self.messages


class AgentStreamFn(Protocol):
    """定义“调用 AI 的函数”应遵循的统一签名。"""

    async def __call__(
        self,
        model: Model | str,
        context: AgentContext,
        thinking: ReasoningLevel | None,
        registry: ProviderRegistry | None = None,
        *,
        signal: AbortSignal | None = None,
    ) -> StreamSession:
        """根据模型、上下文和思考级别返回一个流式会话。"""


class ConvertToLlmFn(Protocol):
    """定义将 Agent 内消息转换为 LLM 消息的钩子签名。"""

    def __call__(
        self,
        messages: list[Any],
        state: AgentState,
    ) -> Awaitable[list[ConversationMessage]] | list[ConversationMessage]:
        """把内部消息列表转换成可送给模型的消息列表。"""


class TransformContextFn(Protocol):
    """定义对模型调用上下文做裁剪或注入的钩子签名。"""

    def __call__(
        self,
        context: AgentContext,
        state: AgentState,
    ) -> Awaitable[AgentContext] | AgentContext:
        """在真正调用模型前变换上下文。"""


ToolUpdateFn: TypeAlias = Callable[[Any], Awaitable[None] | None]


class AgentToolExecutor(Protocol):
    """定义 Agent 工具执行器的统一签名。"""

    def __call__(
        self,
        tool_call_id: str,
        params: Any,
        signal: AbortSignal,
        on_update: ToolUpdateFn,
    ) -> Awaitable[ToolExecutionResult] | ToolExecutionResult:
        """执行工具，并返回标准化前的工具结果。"""


@dataclass(init=False, slots=True)
class AgentTool(Tool):
    """定义可供 Agent 调用的工具。"""

    executor: AgentToolExecutor | None = None

    def __init__(
        self,
        name: str,
        description: str | None = None,
        inputSchema: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        renderMetadata: dict[str, Any] | None = None,
        *,
        executor: AgentToolExecutor | None = None,
        execute: AgentToolExecutor | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.inputSchema = dict(inputSchema or {})
        self.metadata = dict(metadata or {})
        self.renderMetadata = dict(renderMetadata or {})
        self.executor = executor or execute

    @property
    def execute(self) -> AgentToolExecutor | None:
        """兼容旧实现读取 execute。"""

        return self.executor


@dataclass(init=False, slots=True)
class AgentState:
    """定义 Agent 在循环运行中的实时状态。"""

    systemPrompt: str | None = None
    model: Model | str | None = None
    thinking: ReasoningLevel | None = None
    tools: list[AgentTool] = field(default_factory=list)
    messages: list[Any] = field(default_factory=list)
    stream_message: AssistantMessage | None = None
    pending_tool_calls: list[ToolCall] = field(default_factory=list)
    error: AgentError | None = None
    runtime_flags: AgentRuntimeFlags = field(default_factory=AgentRuntimeFlags)

    def __init__(
        self,
        systemPrompt: str | None = None,
        model: Model | str | None = None,
        thinking: ReasoningLevel | None = None,
        tools: list[AgentTool] | None = None,
        messages: list[Any] | None = None,
        stream_message: AssistantMessage | None = None,
        pending_tool_calls: list[ToolCall] | None = None,
        error: AgentError | str | None = None,
        runtime_flags: AgentRuntimeFlags | None = None,
        *,
        history: list[Any] | None = None,
        currentMessage: AssistantMessage | None = None,
        runningToolCall: ToolCall | None = None,
        isStreaming: bool | None = None,
    ) -> None:
        self.systemPrompt = systemPrompt
        self.model = model
        self.thinking = thinking
        self.tools = list(tools or [])
        self.messages = list(messages if messages is not None else (history or []))
        self.stream_message = stream_message if stream_message is not None else currentMessage
        self.pending_tool_calls = list(pending_tool_calls or ([runningToolCall] if runningToolCall is not None else []))
        if isinstance(error, str):
            self.error = AgentError(kind="runtime_error", message=error)
        else:
            self.error = error
        self.runtime_flags = replace(runtime_flags) if runtime_flags is not None else AgentRuntimeFlags()
        if isStreaming is not None:
            self.runtime_flags.isStreaming = isStreaming

    @property
    def history(self) -> list[Any]:
        """兼容旧实现读取 history。"""

        return self.messages

    @property
    def currentMessage(self) -> AssistantMessage | None:
        """兼容旧实现读取 currentMessage。"""

        return self.stream_message

    @property
    def runningToolCall(self) -> ToolCall | None:
        """兼容旧实现读取 runningToolCall。"""

        return self.pending_tool_calls[0] if self.pending_tool_calls else None

    @property
    def isStreaming(self) -> bool:
        """兼容旧实现读取 isStreaming。"""

        return self.runtime_flags.isStreaming


@dataclass(slots=True)
class BeforeToolCallContext:
    """定义 beforeToolCall 收到的上下文信息。"""

    state: AgentState
    tool: AgentTool
    toolCall: ToolCall
    params: Any
    assistantMessage: AssistantMessage | None
    agentContext: AgentContext
    signal: AbortSignal

    @property
    def arguments(self) -> str:
        """兼容旧实现读取字符串参数。"""

        return self.toolCall.arguments_text


@dataclass(slots=True)
class AfterToolCallContext:
    """定义 afterToolCall 收到的上下文信息。"""

    state: AgentState
    tool: AgentTool
    toolCall: ToolCall
    params: Any
    result: ToolResultMessage
    assistantMessage: AssistantMessage | None
    agentContext: AgentContext
    signal: AbortSignal

    @property
    def arguments(self) -> str:
        """兼容旧实现读取字符串参数。"""

        return self.toolCall.arguments_text


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
    details: Any | None = None
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


class GetSteeringMessagesFn(Protocol):
    """定义中途插话消息获取函数的签名。"""

    def __call__(
        self,
        state: AgentState,
        signal: AbortSignal,
    ) -> Awaitable[list[Any]] | list[Any] | None:
        """在 turn 结束后获取 steering 消息。"""


class GetFollowUpMessagesFn(Protocol):
    """定义任务结束后消息获取函数的签名。"""

    def __call__(
        self,
        state: AgentState,
        signal: AbortSignal,
    ) -> Awaitable[list[Any]] | list[Any] | None:
        """在内层循环退出后获取 follow-up 消息。"""


@dataclass(slots=True)
class RetryDecision:
    """定义一次错误后的重试决策。"""

    shouldRetry: bool = False
    delaySeconds: float = 0.0


@dataclass(slots=True)
class RetryContext:
    """定义重试策略收到的上下文。"""

    error: AgentError
    state: AgentState
    attempt: int
    signal: AbortSignal


class RetryPolicyFn(Protocol):
    """定义 provider 错误自动重试策略的签名。"""

    def __call__(
        self,
        context: RetryContext,
    ) -> Awaitable[RetryDecision] | RetryDecision:
        """根据错误上下文决定是否重试。"""


@dataclass(init=False, slots=True)
class AgentLoopConfig:
    """定义 Agent 主循环运行所需的一切配置。"""

    systemPrompt: str | None = None
    model: Model | str | None = None
    thinking: ReasoningLevel | None = None
    tools: list[AgentTool] = field(default_factory=list)
    stream: AgentStreamFn | None = None
    convert_to_llm: ConvertToLlmFn | None = None
    transform_context: TransformContextFn | None = None
    get_steering_messages: GetSteeringMessagesFn | None = None
    get_follow_up_messages: GetFollowUpMessagesFn | None = None
    toolExecutionMode: ToolExecutionMode = "serial"
    beforeToolCall: BeforeToolCallFn | None = None
    afterToolCall: AfterToolCallFn | None = None
    retryPolicy: RetryPolicyFn | None = None
    registry: ProviderRegistry | None = None

    def __init__(
        self,
        systemPrompt: str | None = None,
        model: Model | str | None = None,
        thinking: ReasoningLevel | None = None,
        tools: list[AgentTool] | None = None,
        stream: AgentStreamFn | None = None,
        convert_to_llm: ConvertToLlmFn | None = None,
        transform_context: TransformContextFn | None = None,
        get_steering_messages: GetSteeringMessagesFn | None = None,
        get_follow_up_messages: GetFollowUpMessagesFn | None = None,
        toolExecutionMode: ToolExecutionMode = "serial",
        beforeToolCall: BeforeToolCallFn | None = None,
        afterToolCall: AfterToolCallFn | None = None,
        retryPolicy: RetryPolicyFn | None = None,
        registry: ProviderRegistry | None = None,
        *,
        steer: GetSteeringMessagesFn | None = None,
        followUp: GetFollowUpMessagesFn | None = None,
    ) -> None:
        self.systemPrompt = systemPrompt
        self.model = model
        self.thinking = thinking
        self.tools = list(tools or [])
        self.stream = stream
        self.convert_to_llm = convert_to_llm
        self.transform_context = transform_context
        self.get_steering_messages = get_steering_messages or steer
        self.get_follow_up_messages = get_follow_up_messages or followUp
        self.toolExecutionMode = toolExecutionMode
        self.beforeToolCall = beforeToolCall
        self.afterToolCall = afterToolCall
        self.retryPolicy = retryPolicy
        self.registry = registry

    @property
    def steer(self) -> GetSteeringMessagesFn | None:
        """兼容旧实现读取 steer。"""

        return self.get_steering_messages

    @steer.setter
    def steer(self, value: GetSteeringMessagesFn | None) -> None:
        self.get_steering_messages = value

    @property
    def followUp(self) -> GetFollowUpMessagesFn | None:
        """兼容旧实现读取 followUp。"""

        return self.get_follow_up_messages

    @followUp.setter
    def followUp(self, value: GetFollowUpMessagesFn | None) -> None:
        self.get_follow_up_messages = value


@dataclass(slots=True)
class AgentEvent:
    """定义对外暴露的统一 Agent 事件对象。"""

    type: AgentEventType
    state: AgentState | None = None
    payload: AgentPayload = field(default_factory=dict)

    @property
    def message(self) -> Any:
        """兼容旧实现读取消息对象。"""

        return self.payload.get("message")

    @property
    def messageDelta(self) -> str | None:
        """兼容旧实现读取消息增量。"""

        return self.payload.get("messageDelta")

    @property
    def toolCall(self) -> ToolCall | None:
        """兼容旧实现读取工具调用。"""

        return self.payload.get("toolCall")

    @property
    def toolResult(self) -> ToolResultMessage | None:
        """兼容旧实现读取工具结果。"""

        return self.payload.get("toolResult")

    @property
    def error(self) -> str | None:
        """兼容旧实现读取错误文本。"""

        error = self.payload.get("error")
        if isinstance(error, AgentError):
            return error.message
        if isinstance(error, str):
            return error
        return None


def default_convert_to_llm(messages: list[Any], state: AgentState) -> list[ConversationMessage]:
    """默认把内部消息列表中过滤出的标准对话消息送给模型。"""

    _ = state
    return [message for message in messages if isinstance(message, (AssistantMessage, ToolResultMessage)) or getattr(message, "role", None) == "user"]


def default_transform_context(context: AgentContext, state: AgentState) -> AgentContext:
    """默认直接返回原始上下文，不做额外变换。"""

    _ = state
    return context


def default_retry_policy(context: RetryContext) -> RetryDecision:
    """默认不自动重试。"""

    _ = context
    return RetryDecision(shouldRetry=False, delaySeconds=0.0)


def to_llm_context(state: AgentState, loop: AgentLoopConfig) -> Context:
    """根据当前状态与配置构造真正送给模型的 Context。"""

    convert_fn = loop.convert_to_llm or default_convert_to_llm
    messages = convert_fn(state.messages, state)
    if asyncio.iscoroutine(messages):
        raise RuntimeError("to_llm_context must not be called with async convert_to_llm")
    context = AgentContext(
        systemPrompt=state.systemPrompt,
        messages=list(messages),
        tools=[
            Tool(
                name=tool.name,
                description=tool.description,
                inputSchema=dict(tool.inputSchema),
                metadata=dict(tool.metadata),
                renderMetadata=dict(tool.renderMetadata),
            )
            for tool in state.tools
        ],
    )
    transform_fn = loop.transform_context or default_transform_context
    transformed = transform_fn(context, state)
    if asyncio.iscoroutine(transformed):
        raise RuntimeError("to_llm_context must not be called with async transform_context")
    return Context(systemPrompt=transformed.systemPrompt, messages=transformed.messages, tools=transformed.tools)
