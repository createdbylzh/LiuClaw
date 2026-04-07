from __future__ import annotations

from typing import Any

from ..types import Tool, ensure_tool


def convert_tools_for_provider(tools: list[Tool | dict[str, Any]], target_provider: str | None) -> list[dict[str, Any]]:
    """将统一工具定义转换为目标 provider 兼容的工具字典。"""

    return [_convert_tool(target_provider, ensure_tool(tool)) for tool in tools]



def _convert_tool(provider: str | None, tool: Tool) -> dict[str, Any]:
    """复制工具定义，并记录目标 provider 兼容信息。"""

    metadata = dict(tool.metadata)
    metadata["targetProvider"] = provider
    metadata.setdefault("schemaDialect", "jsonschema")
    return {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": dict(tool.inputSchema),
        "metadata": metadata,
    }
