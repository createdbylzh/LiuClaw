from __future__ import annotations

import json
from pathlib import Path

from agent_core import AgentTool

from ..types import CodingAgentSettings
from .common import resolve_path, truncate_text


def build_read_tool(workspace_root: Path, cwd: Path, settings: CodingAgentSettings) -> AgentTool:
    """构造读取文件内容的内置工具。"""

    async def execute(arguments: str, context) -> str:
        """读取目标文件并按设置做结果截断。"""

        payload = json.loads(arguments or "{}")
        path = resolve_path(cwd, Path(payload["path"]))
        content = path.read_text(encoding="utf-8")
        return truncate_text(content, settings.tool_policy.max_read_chars)

    return AgentTool(
        name="read",
        description="Read a UTF-8 text file from the local filesystem.",
        inputSchema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        execute=execute,
    )
