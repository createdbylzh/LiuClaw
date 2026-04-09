from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from ai.types import AssistantMessage, ConversationMessage, Model
from agent_core import AgentEvent, AgentTool

ReasoningLevel = Literal["low", "medium", "high"]
SessionEventType = Literal[
    "status",
    "thinking",
    "message_start",
    "message_delta",
    "message_end",
    "tool_start",
    "tool_update",
    "tool_end",
    "error",
]
SessionPanel = Literal["main", "status", "thinking", "tool", "error"]
StatusLevel = Literal["info", "success", "warning", "error"]
ToolMode = Literal["workspace-write", "read-only"]


@dataclass(slots=True)
class ToolPolicy:
    """定义内置工具的默认限制与安全策略。"""

    max_read_chars: int = 12000
    max_command_chars: int = 12000
    max_ls_entries: int = 200
    max_find_entries: int = 200
    allow_bash: bool = True


@dataclass(slots=True)
class CodingAgentSettings:
    """定义 coding-agent 运行时使用的合并后设置。"""

    default_model: str = "openai:gpt-5"
    default_thinking: ReasoningLevel = "medium"
    auto_compact: bool = True
    compact_threshold: float = 0.8
    compact_keep_turns: int = 4
    compact_model: str | None = None
    theme: str = "default"
    system_prompt_override: str | None = None
    tool_policy: ToolPolicy = field(default_factory=ToolPolicy)


@dataclass(slots=True)
class SkillResource:
    """表示一个已发现的技能摘要。"""

    name: str
    description: str
    path: Path


@dataclass(slots=True)
class PromptResource:
    """表示一个已加载的提示模板资源。"""

    name: str
    path: Path
    content: str


@dataclass(slots=True)
class ThemeResource:
    """表示一个已加载的主题资源。"""

    name: str
    path: Path
    data: dict[str, Any]


@dataclass(slots=True)
class ExtensionResource:
    """表示一个已扫描但未执行的扩展资源。"""

    name: str
    path: Path
    module_path: Path | None = None
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExtensionCommand:
    """表示扩展注册的一条命令描述。"""

    name: str
    handler: Callable[..., Any] | None = None
    description: str = ""
    source: str = ""


@dataclass(slots=True)
class ExtensionRuntime:
    """表示一次扩展装配后得到的运行时贡献结果。"""

    tools: list[AgentTool] = field(default_factory=list)
    commands: list[ExtensionCommand] = field(default_factory=list)
    provider_factories: dict[str, Callable[..., Any]] = field(default_factory=dict)
    event_listeners: list[Callable[[AgentEvent], Any]] = field(default_factory=list)
    prompt_fragments: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ControlMessage:
    """表示 steering 或 follow-up 这类显式控制消息。"""

    kind: Literal["steering", "follow_up", "custom"]
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolExecutionContext:
    """描述一次工具执行前后可见的安全上下文。"""

    tool_name: str
    workspace_root: Path
    cwd: Path
    arguments: dict[str, Any] = field(default_factory=dict)
    mode: ToolMode = "workspace-write"


@dataclass(slots=True)
class ToolSecurityPolicy:
    """定义工具执行前后的统一安全策略接口。"""

    before_execute: Callable[[ToolExecutionContext], None] | None = None
    after_execute: Callable[[ToolExecutionContext, str], str] | None = None


@dataclass(slots=True)
class ToolDefinition:
    """描述一个可构建的工具定义。"""

    name: str
    description: str
    builder: Callable[[Path, Path, CodingAgentSettings], AgentTool]
    group: str = "general"
    built_in: bool = False
    mode: ToolMode = "workspace-write"
    source: str = "core"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ResourceBundle:
    """聚合一次资源扫描得到的全部资源。"""

    skills: list[SkillResource] = field(default_factory=list)
    prompts: dict[str, PromptResource] = field(default_factory=dict)
    themes: dict[str, ThemeResource] = field(default_factory=dict)
    agents_context: str | None = None
    extensions: list[ExtensionResource] = field(default_factory=list)
    extension_runtime: ExtensionRuntime = field(default_factory=ExtensionRuntime)


@dataclass(slots=True)
class SessionContext:
    """描述构建系统提示时所需的上下文信息。"""

    workspace_root: Path
    cwd: Path
    model: Model
    thinking: ReasoningLevel | None
    settings: CodingAgentSettings
    resources: ResourceBundle
    tools_markdown: str
    extra_prompt_fragments: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SessionEvent:
    """定义给交互层消费的统一会话事件。"""

    type: SessionEventType
    message: str = ""
    delta: str = ""
    tool_name: str = ""
    error: str | None = None
    panel: SessionPanel = "main"
    status_level: StatusLevel = "info"
    is_transient: bool = False
    tool_arguments: str = ""
    tool_output_preview: str = ""
    message_id: str = ""
    turn_id: str = ""
    source: str = ""
    render_group: str = ""
    render_order: int = 0
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PersistedMessageNode:
    """表示落盘后的单条会话节点数据。"""

    id: str
    role: str
    content: str
    parent_id: str | None
    branch_id: str
    message_type: str = "message"
    tool_name: str | None = None
    tool_call_id: str | None = None
    thinking: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SessionSnapshot:
    """表示从会话文件中恢复出的完整快照。"""

    session_id: str
    branch_id: str
    cwd: Path
    model_id: str
    nodes: list[PersistedMessageNode] = field(default_factory=list)
    summaries: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class CompactResult:
    """表示一次上下文压缩的结果。"""

    summary: str
    compacted_count: int
    branch_id: str
    node_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ContextStats:
    """表示当前上下文的粗略 token 统计信息。"""

    estimated_tokens: int
    limit: int
    ratio: float


def assistant_from_parts(content: str, thinking: str = "") -> AssistantMessage:
    """根据文本与思考内容快捷构造 assistant 消息。"""

    return AssistantMessage(content=content, thinking=thinking)


def conversation_to_node_payload(message: ConversationMessage) -> dict[str, Any]:
    """把统一消息对象转换为可持久化的节点载荷。"""

    payload: dict[str, Any] = {
        "role": getattr(message, "role", ""),
        "content": getattr(message, "content", ""),
        "metadata": dict(getattr(message, "metadata", {})),
    }
    if getattr(message, "role", "") == "assistant":
        payload["thinking"] = getattr(message, "thinking", "")
        payload["tool_calls"] = [
            {
                "id": tool_call.id,
                "name": tool_call.name,
                "arguments": tool_call.arguments,
                "metadata": dict(tool_call.metadata),
            }
            for tool_call in getattr(message, "toolCalls", [])
        ]
    if getattr(message, "role", "") == "tool":
        payload["tool_name"] = getattr(message, "toolName", "")
        payload["tool_call_id"] = getattr(message, "toolCallId", "")
    return payload
