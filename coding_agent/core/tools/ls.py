from __future__ import annotations

import json
from pathlib import Path

from agent_core import AgentTool

from ..types import CodingAgentSettings
from .common import ensure_within_workspace


def build_ls_tool(workspace_root: Path, settings: CodingAgentSettings) -> AgentTool:
    """构造列出目录内容的工具。"""

    async def execute(arguments: str, context) -> str:
        """返回目标目录下的直接子项列表。"""

        payload = json.loads(arguments or "{}")
        path = ensure_within_workspace(workspace_root, Path(payload.get("path", ".")))
        entries: list[str] = []
        for child in sorted(path.iterdir()):
            label = child.name + ("/" if child.is_dir() else "")
            entries.append(label)
            if len(entries) >= settings.tool_policy.max_ls_entries:
                break
        return "\n".join(entries)

    return AgentTool(
        name="ls",
        description="List files in a directory.",
        inputSchema={"type": "object", "properties": {"path": {"type": "string"}}, "required": []},
        execute=execute,
    )
