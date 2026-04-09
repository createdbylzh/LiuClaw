from __future__ import annotations

import json
from pathlib import Path

from agent_core import AgentTool

from ..types import CodingAgentSettings
from .common import run_shell, truncate_text


def build_bash_tool(workspace_root: Path, cwd: Path, settings: CodingAgentSettings) -> AgentTool:
    """构造执行 shell 命令的内置工具。"""

    async def execute(arguments: str, context) -> str:
        """执行命令并返回退出码、标准输出与标准错误。"""

        if not settings.tool_policy.allow_bash:
            raise ValueError("bash tool is disabled by settings")
        payload = json.loads(arguments or "{}")
        command = str(payload["command"])
        completed = run_shell(command, cwd)
        output = "\n".join(
            [
                f"$ {command}",
                f"exit_code: {completed.returncode}",
                "stdout:",
                completed.stdout.rstrip(),
                "stderr:",
                completed.stderr.rstrip(),
            ]
        )
        return truncate_text(output, settings.tool_policy.max_command_chars)

    return AgentTool(
        name="bash",
        description="Run a non-interactive shell command in the current working directory.",
        inputSchema={"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
        execute=execute,
    )
