from __future__ import annotations

import json
from pathlib import Path

from agent_core import AgentTool

from ..types import CodingAgentSettings
from .common import resolve_path


def build_edit_tool(workspace_root: Path, cwd: Path, settings: CodingAgentSettings) -> AgentTool:
    """构造支持精确替换和行范围替换的编辑工具。"""

    async def execute(arguments: str, context) -> str:
        """根据替换规则修改目标文件。"""

        payload = json.loads(arguments or "{}")
        path = resolve_path(cwd, Path(payload["path"]))
        content = path.read_text(encoding="utf-8")
        if "old" in payload and "new" in payload:
            if str(payload["old"]) not in content:
                raise ValueError("edit.old not found in file")
            updated = content.replace(str(payload["old"]), str(payload["new"]), 1)
        elif "start_line" in payload and "end_line" in payload and "replacement" in payload:
            lines = content.splitlines()
            start = int(payload["start_line"]) - 1
            end = int(payload["end_line"])
            if start < 0 or end > len(lines) or start >= end:
                raise ValueError("Invalid line range")
            replacement_lines = str(payload["replacement"]).splitlines()
            updated_lines = lines[:start] + replacement_lines + lines[end:]
            updated = "\n".join(updated_lines)
            if content.endswith("\n"):
                updated += "\n"
        else:
            raise ValueError("Unsupported edit payload")
        path.write_text(updated, encoding="utf-8")
        return f"Edited {path}"

    return AgentTool(
        name="edit",
        description="Edit a UTF-8 text file by exact replacement or line range.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old": {"type": "string"},
                "new": {"type": "string"},
                "start_line": {"type": "integer"},
                "end_line": {"type": "integer"},
                "replacement": {"type": "string"},
            },
            "required": ["path"],
        },
        execute=execute,
    )
