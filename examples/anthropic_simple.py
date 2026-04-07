import asyncio

from ai import Context, ToolResultMessage, UserMessage, get_model, stream
from ai.registry import ProviderRegistry
from ai.providers.anthropic import AnthropicProvider


async def main() -> None:
    registry = ProviderRegistry()
    registry.register_factory("anthropic", AnthropicProvider)

    session = await stream(
        model=get_model("anthropic:claude-sonnet-4"),
        context=Context(
            systemPrompt="你是一个技术文档助手。",
            messages=[
                UserMessage(content="解释一下 done 事件为什么要携带完整最终结果。"),
                ToolResultMessage(
                    toolCallId="call_1",
                    toolName="lookup_spec",
                    content='{"summary":"统一事件协议降低了上层复杂度"}',
                ),
            ],
            tools=[],
        ),
        registry=registry,
    )
    async for event in session.consume():
        if event.type == "text_delta":
            print(event.text, end="")
        if event.type == "done":
            print()
            print(event.assistantMessage.thinking)
            break
        if event.type == "error":
            raise RuntimeError(event.error)


if __name__ == "__main__":
    asyncio.run(main())
