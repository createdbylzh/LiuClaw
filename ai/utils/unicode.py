from __future__ import annotations

import unicodedata

from ai.types import (
    AssistantMessage,
    Context,
    ImageContent,
    TextContent,
    ThinkingContent,
    Tool,
    ToolCall,
    ToolCallContent,
    ToolResultContent,
    ToolResultMessage,
    UserMessage,
)

_DISALLOWED_CATEGORIES = {"Cc", "Cf"}
_ALLOWED_CONTROL_CHARACTERS = {"\n", "\r", "\t"}


def sanitize_unicode(text: str) -> str:
    """对文本做安全 Unicode 规范化，并移除危险控制字符。"""
    normalized = unicodedata.normalize("NFKC", text)
    cleaned_chars: list[str] = []
    for char in normalized:
        if char in _ALLOWED_CONTROL_CHARACTERS:
            cleaned_chars.append(char)
            continue
        if unicodedata.category(char) in _DISALLOWED_CATEGORIES:
            continue
        cleaned_chars.append(char)
    return "".join(cleaned_chars)


def sanitize_unicode_context(context: Context) -> Context:
    """返回一个完成 Unicode 清理的新 `Context`。"""
    return Context(
        systemPrompt=sanitize_unicode(context.systemPrompt) if context.systemPrompt else context.systemPrompt,
        messages=[_sanitize_message(message) for message in context.messages],
        tools=[_sanitize_tool(tool) for tool in context.tools],
    )


def _sanitize_message(message: UserMessage | AssistantMessage | ToolResultMessage):
    """清理统一消息对象中的文本字段。"""
    if isinstance(message, UserMessage):
        return UserMessage(
            content=[_sanitize_content_block(block) for block in message.content],
            metadata=dict(message.metadata),
            timestamp=message.timestamp,
        )
    if isinstance(message, AssistantMessage):
        return AssistantMessage(
            content=[_sanitize_content_block(block) for block in message.content],
            metadata=dict(message.metadata),
            usage=dict(message.usage) if message.usage is not None else None,
            stopReason=message.stopReason,
            responseId=message.responseId,
            errorMessage=message.errorMessage,
            timestamp=message.timestamp,
        )
    return ToolResultMessage(
        toolCallId=sanitize_unicode(message.toolCallId),
        toolName=sanitize_unicode(message.toolName),
        content=[_sanitize_content_block(block) for block in message.content],
        metadata=dict(message.metadata),
        isError=message.isError,
        details=message.details,
        timestamp=message.timestamp,
    )


def _sanitize_tool(tool: Tool) -> Tool:
    """清理工具定义中的文本字段。"""
    return Tool(
        name=sanitize_unicode(tool.name),
        description=sanitize_unicode(tool.description) if tool.description is not None else None,
        inputSchema=dict(tool.inputSchema),
        metadata=dict(tool.metadata),
    )


def _sanitize_tool_call(tool_call: ToolCall) -> ToolCall:
    """清理工具调用对象中的文本字段。"""
    return ToolCall(
        id=sanitize_unicode(tool_call.id),
        name=sanitize_unicode(tool_call.name),
        arguments=sanitize_unicode(tool_call.arguments),
        metadata=dict(tool_call.metadata),
    )


def _sanitize_content_block(block):
    """清理内容块中的文本字段。"""

    if isinstance(block, TextContent):
        return TextContent(text=sanitize_unicode(block.text))
    if isinstance(block, ThinkingContent):
        return ThinkingContent(thinking=sanitize_unicode(block.thinking))
    if isinstance(block, ToolCallContent):
        return ToolCallContent(
            id=sanitize_unicode(block.id),
            name=sanitize_unicode(block.name),
            arguments=sanitize_unicode(block.arguments_text),
            metadata=dict(block.metadata),
        )
    if isinstance(block, ToolResultContent):
        return ToolResultContent(
            text=sanitize_unicode(block.text),
            data=block.data,
            mimeType=block.mimeType,
            metadata=dict(block.metadata),
        )
    if isinstance(block, ImageContent):
        return ImageContent(
            data=block.data,
            mimeType=block.mimeType,
            detail=block.detail,
            metadata=dict(block.metadata),
        )
    return block
