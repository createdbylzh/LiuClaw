from __future__ import annotations

import json
from pathlib import Path

from agent_core import AgentTool

from ..types import CodingAgentSettings
from .common import resolve_path


def build_find_tool(workspace_root: Path, cwd: Path, settings: CodingAgentSettings) -> AgentTool:
    """构造按文件名片段查找路径的工具。"""

    async def execute(arguments: str, context) -> str:
        """递归查找匹配名称的文件或目录。"""

        payload = json.loads(arguments or "{}")
        pattern = str(payload.get("pattern", ""))
        base = resolve_path(cwd, Path(payload.get("path", ".")))
        matches: list[str] = []
        for path in sorted(base.rglob("*")):
            if pattern and pattern not in path.name:
                continue
            matches.append(str(path))
            if len(matches) >= settings.tool_policy.max_find_entries:
                break
        return "\n".join(matches)

    return AgentTool(
        name="find",
        description="Find files by name fragment on the local filesystem.",
        inputSchema={
            "type": "object",
            "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}},
            "required": [],
        },
        execute=execute,
    )
