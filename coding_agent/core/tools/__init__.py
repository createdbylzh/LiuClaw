from __future__ import annotations

from pathlib import Path

from agent_core import AgentTool

from ..types import CodingAgentSettings
from .bash import build_bash_tool
from .edit import build_edit_tool
from .find import build_find_tool
from .grep import build_grep_tool
from .ls import build_ls_tool
from .read import build_read_tool
from .write import build_write_tool


def build_default_tools(workspace_root: Path, settings: CodingAgentSettings) -> list[AgentTool]:
    """构造 coding-agent 默认启用的全部内置工具。"""

    return [
        build_read_tool(workspace_root, settings),
        build_write_tool(workspace_root, settings),
        build_edit_tool(workspace_root, settings),
        build_bash_tool(workspace_root, settings),
        build_grep_tool(workspace_root, settings),
        build_find_tool(workspace_root, settings),
        build_ls_tool(workspace_root, settings),
    ]


def render_tools_markdown(tools: list[AgentTool]) -> str:
    """把工具列表渲染成系统提示可用的 Markdown 文本。"""

    lines = []
    for tool in tools:
        lines.append(f"- {tool.name}: {tool.description or ''}")
    return "\n".join(lines)
