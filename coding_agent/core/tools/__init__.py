from __future__ import annotations

from pathlib import Path

from agent_core import AgentTool

from ..types import CodingAgentSettings, ToolDefinition
from .bash import build_bash_tool
from .edit import build_edit_tool
from .find import build_find_tool
from .grep import build_grep_tool
from .ls import build_ls_tool
from .read import build_read_tool
from .registry import ToolRegistry
from .security import build_default_tool_security_policy
from .write import build_write_tool


def build_default_tool_definitions() -> list[ToolDefinition]:
    """返回全部内置工具定义。"""

    return [
        ToolDefinition(name="read", description="Read a UTF-8 text file inside the workspace.", builder=build_read_tool, group="filesystem", built_in=True, mode="read-only"),
        ToolDefinition(name="write", description="Write UTF-8 text to a file inside the workspace.", builder=build_write_tool, group="filesystem", built_in=True, mode="workspace-write"),
        ToolDefinition(name="edit", description="Edit a file by exact replacement or line range.", builder=build_edit_tool, group="filesystem", built_in=True, mode="workspace-write"),
        ToolDefinition(name="bash", description="Run a non-interactive shell command in the workspace.", builder=build_bash_tool, group="shell", built_in=True, mode="workspace-write"),
        ToolDefinition(name="grep", description="Search text in files using ripgrep.", builder=build_grep_tool, group="search", built_in=True, mode="read-only"),
        ToolDefinition(name="find", description="Find files by name fragment inside the workspace.", builder=build_find_tool, group="search", built_in=True, mode="read-only"),
        ToolDefinition(name="ls", description="List files in a directory.", builder=build_ls_tool, group="filesystem", built_in=True, mode="read-only"),
    ]


def build_tool_registry(workspace_root: Path, settings: CodingAgentSettings) -> ToolRegistry:
    """构造并填充默认工具注册表。"""

    registry = ToolRegistry(workspace_root, settings, security_policy=build_default_tool_security_policy(workspace_root, settings))
    for definition in build_default_tool_definitions():
        registry.register_definition(definition)
    return registry


def build_default_tools(workspace_root: Path, settings: CodingAgentSettings) -> list[AgentTool]:
    """构造 coding-agent 默认启用的全部内置工具。"""

    return build_tool_registry(workspace_root, settings).activate_all()


def render_tools_markdown(tools: list[AgentTool]) -> str:
    """把工具列表渲染成系统提示可用的 Markdown 文本。"""

    lines = []
    for tool in tools:
        group = tool.metadata.get("group", "general")
        lines.append(f"- {tool.name}: {tool.description or ''} [group={group}]")
    return "\n".join(lines)


__all__ = [
    "ToolRegistry",
    "build_default_tool_definitions",
    "build_default_tools",
    "build_tool_registry",
    "render_tools_markdown",
]
