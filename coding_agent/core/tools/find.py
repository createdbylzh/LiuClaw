from __future__ import annotations

import json
from pathlib import Path

from agent_core import AgentTool

from ..types import CodingAgentSettings
from .common import ensure_within_workspace


def build_find_tool(workspace_root: Path, settings: CodingAgentSettings) -> AgentTool:
    """构造按文件名片段查找路径的工具。"""

    async def execute(arguments: str, context) -> str:
        """递归查找匹配名称的文件或目录。"""

        payload = json.loads(arguments or "{}")
        pattern = str(payload.get("pattern", ""))
        base = ensure_within_workspace(workspace_root, Path(payload.get("path", ".")))
        matches: list[str] = []
        for path in sorted(base.rglob("*")):
            if pattern and pattern not in path.name:
                continue
            matches.append(str(path.relative_to(workspace_root)))
            if len(matches) >= settings.tool_policy.max_find_entries:
                break
        return "\n".join(matches)

    return AgentTool(
        name="find",
        description="Find files by name fragment inside the workspace.",
        inputSchema={
            "type": "object",
            "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}},
            "required": [],
        },
        execute=execute,
    )
