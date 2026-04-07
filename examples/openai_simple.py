import asyncio

from ai import Context, Tool, UserMessage, stream
from ai.registry import ProviderRegistry
from ai.providers.openai import OpenAIProvider


async def main() -> None:
    registry = ProviderRegistry()
    registry.register_factory("openai", OpenAIProvider)

    session = await stream(
        model="openai:gpt-5",
        context=Context(
            systemPrompt="你是一个简洁的中文助手。",
            messages=[
                UserMessage(content="请用一句话介绍统一 LLM 接入层。"),
            ],
            tools=[
                Tool(
                    name="lookup_spec",
                    description="查询规格说明",
                    inputSchema={
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                )
            ],
        ),
        registry=registry,
    )
    async for event in session.consume():
        if event.type == "text_delta":
            print(event.text, end="")
        if event.type == "done":
            print()
            print(event.assistantMessage.thinking)
            print(event.assistantMessage.toolCalls)
            break
        if event.type == "error":
            raise RuntimeError(event.error)


if __name__ == "__main__":
    asyncio.run(main())
