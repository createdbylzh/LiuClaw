from __future__ import annotations

import json
from pathlib import Path

from agent_core import AgentTool

from ..types import CodingAgentSettings
from .common import resolve_path


def build_write_tool(workspace_root: Path, cwd: Path, settings: CodingAgentSettings) -> AgentTool:
    """构造写入文件内容的内置工具。"""

    async def execute(arguments: str, context) -> str:
        """把给定文本写入工作区内的目标文件。"""

        payload = json.loads(arguments or "{}")
        path = resolve_path(cwd, Path(payload["path"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(payload.get("content", "")), encoding="utf-8")
        return f"Wrote {path}"

    return AgentTool(
        name="write",
        description="Write UTF-8 text to a file on the local filesystem.",
        inputSchema={
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
        execute=execute,
    )
