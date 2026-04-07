from __future__ import annotations

import json
from pathlib import Path

from agent_core import AgentTool

from ..types import CodingAgentSettings
from .common import ensure_within_workspace, run_shell, truncate_text


def build_grep_tool(workspace_root: Path, settings: CodingAgentSettings) -> AgentTool:
    """构造基于 ripgrep 的文本搜索工具。"""

    async def execute(arguments: str, context) -> str:
        """在工作区内搜索匹配文本并返回结果。"""

        payload = json.loads(arguments or "{}")
        pattern = str(payload["pattern"])
        search_path = ensure_within_workspace(workspace_root, Path(payload.get("path", ".")))
        command = f"rg -n --no-heading {json.dumps(pattern)} {json.dumps(str(search_path))}"
        completed = run_shell(command, workspace_root)
        output = completed.stdout or completed.stderr
        return truncate_text(output.strip(), settings.tool_policy.max_read_chars)

    return AgentTool(
        name="grep",
        description="Search text in files using ripgrep.",
        inputSchema={
            "type": "object",
            "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}},
            "required": ["pattern"],
        },
        execute=execute,
    )
