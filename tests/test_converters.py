from ai import AssistantMessage, Context, Tool, ToolCall, ToolResultMessage, UserMessage
from ai.converters.messages import convert_messages_for_provider
from ai.converters.tools import convert_tools_for_provider


def test_message_converter_preserves_cross_provider_history() -> None:
    messages = [
        UserMessage(content="请继续上一轮对话"),
        AssistantMessage(
            content="我先调用工具。",
            thinking="需要读取规格",
            toolCalls=[ToolCall(id="call_1", name="lookup_spec", arguments='{"query":"api"}')],
        ),
        ToolResultMessage(
            toolCallId="call_1",
            toolName="lookup_spec",
            content='{"title":"统一接口说明"}',
        ),
    ]

    converted = convert_messages_for_provider(messages, target_provider="anthropic")

    assert converted
    assert len(converted) == 3


def test_tool_converter_preserves_schema_for_target_provider() -> None:
    tools = [
        Tool(
            name="lookup_spec",
            description="查询规格说明",
            inputSchema={"type": "object", "properties": {"query": {"type": "string"}}},
        )
    ]

    converted = convert_tools_for_provider(tools, target_provider="openai")

    assert converted
    assert converted[0]["name"] == "lookup_spec"
