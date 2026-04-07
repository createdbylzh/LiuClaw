# ai

面向上层业务的统一 LLM 接入层。

这个模块将不同厂商的大模型能力统一为一套 async API，并围绕以下核心概念组织：
- `Context`：一次请求的完整上下文，包含 `systemPrompt`、`messages`、`tools`
- `Model`：统一模型描述，包含模型 ID、价格、上下文窗口等元数据
- `StreamEvent`：统一流式事件协议，覆盖文本、thinking、tool call、done、error
- `StreamSession`：队列化流式会话对象，负责承载 producer task 和事件队列
- `ProviderRegistry`：按 provider 名懒加载适配器的注册中心
- `ai.converters.*`：处理跨 provider 的历史消息与工具兼容转换
- `ai.utils.*`：提供流式聚合、schema 校验、上下文溢出检测、Unicode 清理等基础设施

## Install

```bash
uv sync
```

## Core API

- `stream(model, context, options)`：返回 `StreamSession`
- `complete(model, context, options)`：消费 session queue，一次性拿到最终 `AssistantMessage`
- `streamSimple(model, context, ...)`：返回简化参数版 `StreamSession`
- `completeSimple(model, context, ...)`：基于 queue 聚合最终结果
- `get_model(model_id)`：从内置模型目录中获取 `Model`
- `list_models(provider=None)`：列出内置模型目录，可按 provider 过滤

## Agent Runtime

`agent_core` 建立在 `ai` 之上，提供两层新的运行时 API：
- 低层：`agentLoop()` / `agentLoopContinue()`
- 高层：`Agent`

运行配置按三层拆分：
- `AgentLoopConfig`：主循环配置，包含模型、system prompt、工具、steer/followUp 与工具钩子
- `AgentContext`：一次 AI / 工具调用时使用的上下文快照
- `AgentStreamFn`：底层流式函数签名，默认走 `streamSimple`

### `agentLoop()` Example

```python
import asyncio

from ai import UserMessage
from agent_core import AgentLoopConfig, AgentTool, agentLoop


async def lookup(arguments: str, context) -> str:
    await context.reportProgress("searching")
    return '{"result":"ok"}'


async def main() -> None:
    async for event in agentLoop(
        AgentLoopConfig(
            model="openai:gpt-5",
            systemPrompt="你是一个可以调用工具的技术助手。",
            tools=[
                AgentTool(
                    name="lookup_spec",
                    description="查询规格说明",
                    inputSchema={
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                    execute=lookup,
                )
            ],
        ),
        initialMessages=[UserMessage(content="请查一下规格说明")],
    ):
        if event.type == "message_update":
            print(event.messageDelta, end="")
        elif event.type == "tool_execution_end":
            print("\nTOOL:", event.toolResult.content)


asyncio.run(main())
```

### `Agent` Example

```python
import asyncio

from ai import UserMessage
from agent_core import Agent, AgentLoopConfig


async def main() -> None:
    agent = Agent(
        AgentLoopConfig(
            model="anthropic:claude-sonnet-4",
            systemPrompt="你是一个中文文档助手。",
        )
    )
    await agent.send(UserMessage(content="帮我总结一下这个模块"))

    async for event in agent.run():
        if event.type == "message_update":
            print(event.messageDelta, end="")

    print("\nLAST:", agent.lastMessage.content)


asyncio.run(main())
```

## Context Example

```python
from ai import Context, Tool, UserMessage

context = Context(
    systemPrompt="你是一个负责总结需求的助手。",
    messages=[
        UserMessage(content="请用一句话总结这个模块的目标。"),
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
)
```

## Queue Streaming Example

```python
import asyncio

from ai import Context, Tool, UserMessage, stream


async def main() -> None:
    session = await stream(
        model="openai:gpt-5",
        context=Context(
            systemPrompt="你是一个简洁的中文助手。",
            messages=[UserMessage(content="请流式介绍统一 LLM 接入层。")],
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
    )

    async for event in session.consume():
        if event.type == "text_delta":
            print(event.text, end="")
        if event.type in {"done", "error"}:
            break


asyncio.run(main())
```

## `completeSimple()` With Queue Runtime

```python
import asyncio

from ai import Context, ToolResultMessage, UserMessage, completeSimple, get_model


async def main() -> None:
    message = await completeSimple(
        model=get_model("anthropic:claude-sonnet-4"),
        context=Context(
            systemPrompt="你是一个技术文档助手。",
            messages=[
                UserMessage(content="解释一下为什么 stream 要返回队列会话。"),
                ToolResultMessage(
                    toolCallId="call_1",
                    toolName="lookup_spec",
                    content='{"summary":"队列可以隔离生产和消费速度"}',
                ),
            ],
            tools=[],
        ),
        reasoning="medium",
        max_tokens=300,
    )
    print(message.content)
    print(message.thinking)


asyncio.run(main())
```

## Lazy Registry

推荐通过懒加载 registry 管理 provider：

```python
from ai.registry import ProviderRegistry
from ai.providers.openai import OpenAIProvider
from ai.providers.anthropic import AnthropicProvider

registry = ProviderRegistry()
registry.register_factory("openai", OpenAIProvider)
registry.register_factory("anthropic", AnthropicProvider)
```

`resolve(model)` 应在首次命中 provider 时才实例化适配器，并缓存后续复用。

## Queue Model

上层语义现在以生产者-消费者模式为主：
- provider 仍可产出 async iterator 事件
- client 负责把 provider 事件桥接到有界 queue
- 上层直接从 `StreamSession.queue` 或 `StreamSession.consume()` 取事件
- 结束仍通过 `done` / `error` 事件表达，不引入额外哨兵对象

推荐约束：
- queue 为有界队列
- 消费者慢时触发背压
- `done.assistantMessage` 与 `complete()` 返回值语义一致

## Cross-Provider Conversion

当 `Context.messages` 中包含来自其他 provider 的 assistant/tool 历史消息时，调用链应在进入目标 provider 前完成兼容转换。建议由 `ai.converters.messages` 与 `ai.converters.tools` 统一处理：

- 历史 `AssistantMessage.toolCalls` 转成目标 provider 可消费格式
- `ToolResultMessage` 转成目标 provider 所需 tool result 形态
- `Tool.inputSchema` 转成目标 provider 请求结构
- 不支持保真的字段按约定降级，而不是让 provider 请求直接失效

## Reasoning Mapping

统一 `reasoning` 级别：
- `low`
- `medium`
- `high`

在运行时应通过 `ai.reasoning` 映射到各 provider 的具体参数：
- OpenAI：`reasoning.effort`
- Anthropic：`thinking.budget_tokens`

## Utils

`ai.utils` 目录应至少包含这些模块：
- `ai.utils.streaming`：统一事件构造、queue 辅助与 `done` 聚合
- `ai.utils.schema_validation`：AJV 等价的 Python JSON Schema 校验能力
- `ai.utils.context_window`：上下文窗口估算与溢出检测
- `ai.utils.unicode`：安全规范化、零宽/控制字符清理

推荐能力接口：
- `validate_tool_arguments(tool, arguments)`
- `detect_context_overflow(model, context, options)`
- `sanitize_unicode(text)`

## Streaming Event Protocol

统一事件类型如下：
- `start`
- `text_start`
- `text_delta`
- `text_end`
- `thinking_start`
- `thinking_delta`
- `thinking_end`
- `toolcall_start`
- `toolcall_delta`
- `toolcall_end`
- `done`
- `error`

`done` 事件必须携带完整最终结果对象，因此流式调用方可以直接消费 `done`，而 `complete()` 则会基于相同协议做聚合。

## Public Types

推荐上层直接依赖这些公开类型：
- `Context`
- `UserMessage`
- `AssistantMessage`
- `ToolResultMessage`
- `Tool`
- `ToolCall`
- `Model`
- `Options`
- `StreamEvent`
- `StreamSession`
- `AgentState`
- `AgentEvent`
- `AgentLoopConfig`
- `AgentContext`
- `AgentStreamFn`
- `AgentTool`

## Documentation Notes

该模块面向上层团队使用，公共函数应提供中文 docstring，至少覆盖：
- 函数用途
- 参数含义
- 返回值
- 异常或使用注意事项

如果某个公开 API 缺少中文 docstring，应视为待补齐项。
