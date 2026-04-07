from __future__ import annotations

import json
from pathlib import Path

from agent_core import AgentTool

from ..types import CodingAgentSettings
from .common import ensure_within_workspace


def build_write_tool(workspace_root: Path, settings: CodingAgentSettings) -> AgentTool:
    """构造写入文件内容的内置工具。"""

    async def execute(arguments: str, context) -> str:
        """把给定文本写入工作区内的目标文件。"""

        payload = json.loads(arguments or "{}")
        path = ensure_within_workspace(workspace_root, Path(payload["path"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(payload.get("content", "")), encoding="utf-8")
        return f"Wrote {path.relative_to(workspace_root)}"

    return AgentTool(
        name="write",
        description="Write UTF-8 text to a file inside the workspace.",
        inputSchema={
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
        execute=execute,
    )
