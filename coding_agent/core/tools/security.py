from __future__ import annotations

from pathlib import Path

from ..types import CodingAgentSettings, ToolExecutionContext, ToolSecurityPolicy


def build_default_tool_security_policy(workspace_root: Path, settings: CodingAgentSettings) -> ToolSecurityPolicy:
    """构造默认工具安全策略。"""

    def before_execute(context: ToolExecutionContext) -> None:
        write_tools = {"write", "edit"}
        if context.tool_name == "bash" and not settings.tool_policy.allow_bash:
            raise ValueError("bash tool is disabled by settings")
        if context.mode == "read-only" and context.tool_name in write_tools.union({"bash"}):
            raise ValueError(f"{context.tool_name} is blocked in read-only mode")
        if not str(context.workspace_root):
            raise ValueError("workspace root is required for tool execution")

    def after_execute(context: ToolExecutionContext, output: str) -> str:
        _ = context
        return output

    return ToolSecurityPolicy(before_execute=before_execute, after_execute=after_execute)
