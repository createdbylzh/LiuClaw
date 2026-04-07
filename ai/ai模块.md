# ai 模块说明文档

## 1. 模块定位

`ai` 模块是一个面向上层业务的“统一 LLM 接入层”。

它的目标是把不同大模型厂商的调用方式统一为一套稳定的 Python 异步接口，让上层业务不需要直接理解每个厂商 SDK 的差异、流式事件差异、推理参数差异和工具调用差异。

当前模块已经接入以下 provider：

- `openai`
- `anthropic`
- `zhipu`

当前模块采用以下设计原则：

- `async` 优先
- 队列式流式消费优先
- 上层只理解统一类型，不直接处理厂商原始协议
- `complete()` 基于 `stream()` 聚合，避免两套行为分叉
- provider 只负责“协议适配”，不负责上层会话管理

---

## 2. 对外公共能力

模块根导出位于 [__init__.py](/Users/admin/PyCharmProject/LiuClaw/ai/__init__.py)。

### 2.1 主要函数

- `stream(model, context, options=None)`
- `complete(model, context, options=None)`
- `streamSimple(...)`
- `completeSimple(...)`

### 2.2 主要公共类型

- `Context`
- `UserMessage`
- `AssistantMessage`
- `ToolResultMessage`
- `Tool`
- `ToolCall`
- `Model`
- `StreamEvent`
- `Options`
- `ReasoningConfig`
- `StreamSession`

### 2.3 主要异常

- `AIError`
- `ProviderNotFoundError`
- `AuthenticationError`
- `UnsupportedFeatureError`
- `ProviderResponseError`

---

## 3. 模块目录结构

```text
ai/
  __init__.py
  client.py
  errors.py
  models.py
  options.py
  reasoning.py
  registry.py
  session.py
  types.py
  converters/
    messages.py
    tools.py
  providers/
    base.py
    openai.py
    anthropic.py
    zhipu.py
  utils/
    context_window.py
    schema_validation.py
    streaming.py
    unicode.py
```

各文件职责如下：

- [client.py](/Users/admin/PyCharmProject/LiuClaw/ai/client.py): 对外统一入口，负责准备上下文、准备配置、路由 provider、创建流式会话、聚合最终结果。
- [types.py](/Users/admin/PyCharmProject/LiuClaw/ai/types.py): 核心统一类型定义。
- [options.py](/Users/admin/PyCharmProject/LiuClaw/ai/options.py): 调用选项与 reasoning 配置定义。
- [models.py](/Users/admin/PyCharmProject/LiuClaw/ai/models.py): 内置模型目录。
- [reasoning.py](/Users/admin/PyCharmProject/LiuClaw/ai/reasoning.py): 统一 reasoning 到 provider 专用参数的映射层。
- [registry.py](/Users/admin/PyCharmProject/LiuClaw/ai/registry.py): provider 懒加载注册中心。
- [session.py](/Users/admin/PyCharmProject/LiuClaw/ai/session.py): 队列式流式会话封装。
- [providers/base.py](/Users/admin/PyCharmProject/LiuClaw/ai/providers/base.py): provider 抽象接口。
- [providers/openai.py](/Users/admin/PyCharmProject/LiuClaw/ai/providers/openai.py): OpenAI 适配器。
- [providers/anthropic.py](/Users/admin/PyCharmProject/LiuClaw/ai/providers/anthropic.py): Anthropic 适配器。
- [providers/zhipu.py](/Users/admin/PyCharmProject/LiuClaw/ai/providers/zhipu.py): 智谱 GLM 适配器。
- [converters/messages.py](/Users/admin/PyCharmProject/LiuClaw/ai/converters/messages.py): 跨 provider 消息兼容转换。
- [converters/tools.py](/Users/admin/PyCharmProject/LiuClaw/ai/converters/tools.py): 工具定义兼容转换。
- [utils/streaming.py](/Users/admin/PyCharmProject/LiuClaw/ai/utils/streaming.py): 流式事件构造、聚合和队列辅助。
- [utils/context_window.py](/Users/admin/PyCharmProject/LiuClaw/ai/utils/context_window.py): 上下文窗口估算与溢出检测。
- [utils/schema_validation.py](/Users/admin/PyCharmProject/LiuClaw/ai/utils/schema_validation.py): 工具参数 JSON Schema 校验。
- [utils/unicode.py](/Users/admin/PyCharmProject/LiuClaw/ai/utils/unicode.py): Unicode 清理与规范化。

---

## 4. 核心类型说明

核心类型定义位于 [types.py](/Users/admin/PyCharmProject/LiuClaw/ai/types.py)。

### 4.1 Context

`Context` 表示一次调用的统一上下文。

```python
@dataclass(slots=True)
class Context:
    systemPrompt: str | None = None
    messages: list[ConversationMessage] = field(default_factory=list)
    tools: list[Tool] = field(default_factory=list)
```

字段说明：

- `systemPrompt`: 系统提示词。
- `messages`: 历史对话消息。
- `tools`: 本轮可用工具定义。

注意事项：

- 完整版接口统一要求传 `Context` 或能被规范化为 `Context` 的字典。
- `Context` 中不直接保存 provider 原始消息结构。

### 4.2 Message 类型

当前没有单一 `Message` 类，而是显式拆成三种消息类型。

#### UserMessage

表示用户消息。

```python
UserMessage(
    content="你好",
    metadata={},
)
```

#### AssistantMessage

表示 assistant 输出消息，也是 `complete()` 的最终返回对象。

```python
AssistantMessage(
    content="最终文本",
    thinking="模型思考内容",
    toolCalls=[...],
    metadata={},
)
```

字段说明：

- `content`: 最终文本内容。
- `thinking`: 统一抽象后的思考内容。
- `toolCalls`: assistant 发起的工具调用列表。
- `metadata`: provider 原始响应或额外信息。

`AssistantMessage.text` 是 `content` 的别名属性。

#### ToolResultMessage

表示工具执行后的结果回填消息。

```python
ToolResultMessage(
    toolCallId="call_1",
    toolName="lookup_weather",
    content='{"temp": 26}',
)
```

字段说明：

- `toolCallId`: 对应 assistant 发起的工具调用 ID。
- `toolName`: 工具名。
- `content`: 工具执行结果文本。

### 4.3 Tool 与 ToolCall

#### Tool

表示上层提供给模型的工具定义。

```python
Tool(
    name="lookup_weather",
    description="查询天气",
    inputSchema={"type": "object", "properties": {...}},
)
```

#### ToolCall

表示 assistant 在响应中生成的一次工具调用。

```python
ToolCall(
    id="call_1",
    name="lookup_weather",
    arguments='{"city":"Shanghai"}',
)
```

注意：

- `Tool` 是工具定义。
- `ToolCall` 是模型发起的调用。
- `ToolResultMessage` 是工具执行结果回填。
- 三者不是同一个概念。

### 4.4 Model

`Model` 表示统一模型元数据。

```python
@dataclass(slots=True)
class Model:
    id: str
    provider: str
    inputPrice: float
    outputPrice: float
    contextWindow: int
    maxOutputTokens: int
    metadata: dict[str, Any] = field(default_factory=dict)
```

字段说明：

- `id`: 统一模型 ID，例如 `openai:gpt-5`。
- `provider`: provider 名称，例如 `openai`。
- `inputPrice`: 输入价格。
- `outputPrice`: 输出价格。
- `contextWindow`: 上下文窗口大小。
- `maxOutputTokens`: 模型最大输出 token 预算。
- `metadata`: 额外元数据。

对于 `zhipu` 模型，当前价格字段使用占位值 `0.0`，并在 `metadata.priceStatus` 中标记为 `needs_manual_sync`。

### 4.5 StreamEvent

`StreamEvent` 表示统一流式事件对象。

```python
@dataclass(slots=True)
class StreamEvent:
    type: StreamEventType
    model: Model | None = None
    provider: str | None = None
    text: str | None = None
    thinking: str | None = None
    toolCallId: str | None = None
    toolName: str | None = None
    argumentsDelta: str | None = None
    arguments: str | None = None
    assistantMessage: AssistantMessage | None = None
    usage: dict[str, Any] | None = None
    stopReason: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    rawEvent: Any | None = None
```

当前支持的事件类型：

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

字段说明：

- `text`: 文本增量。
- `thinking`: 思考增量。
- `toolCallId`: 工具调用 ID。
- `toolName`: 工具名。
- `argumentsDelta`: 工具参数增量。
- `arguments`: 工具参数最终值。
- `assistantMessage`: `done` 事件中的最终完整消息。
- `usage`: token 使用量等元数据。
- `stopReason`: 停止原因。
- `error`: 错误文本。
- `rawEvent`: 可选原始 provider 事件。

---

## 5. Options 与 reasoning

定义位于 [options.py](/Users/admin/PyCharmProject/LiuClaw/ai/options.py)。

### 5.1 Options

```python
Options(
    reasoning="high",
    temperature=0.2,
    maxTokens=4096,
    metadata={},
    timeout=30,
    includeRawProviderEvents=False,
    streamQueueMaxSize=64,
    streamPutTimeout=None,
)
```

字段说明：

- `reasoning`: 统一 reasoning 等级，支持 `low`、`medium`、`high`，也支持 `ReasoningConfig`。
- `temperature`: 温度参数。
- `maxTokens`: 期望最大输出 token 数。
- `metadata`: 附加元数据，也用于传递 provider 专用 reasoning 映射结果。
- `timeout`: 请求超时。
- `includeRawProviderEvents`: 是否保留原始 provider 事件到 `rawEvent`。
- `streamQueueMaxSize`: 流式队列最大长度。
- `streamPutTimeout`: producer 写队列超时。

### 5.2 ReasoningConfig

```python
ReasoningConfig(effort="medium")
```

本质上是对 `low/medium/high` 的结构化封装。

### 5.3 reasoning 映射规则

映射逻辑位于 [reasoning.py](/Users/admin/PyCharmProject/LiuClaw/ai/reasoning.py)。

当前规则如下：

#### OpenAI

- `low -> {"reasoning": {"effort": "low"}}`
- `medium -> {"reasoning": {"effort": "medium"}}`
- `high -> {"reasoning": {"effort": "high"}}`

#### Anthropic

- `low -> thinking budget 1024`
- `medium -> thinking budget 4096`
- `high -> thinking budget 8192`

#### Zhipu

- `low -> {"thinking": {"type": "disabled"}}`
- `medium -> {"thinking": {"type": "enabled"}}`
- `high -> glm-4.6` 降级为 `{"thinking": {"type": "enabled"}}`
- `high -> 其他 zhipu 模型` 为 `{"thinking": {"type": "enabled"}, "clear_thinking": False}`

`client` 会把上述映射结果写入 `options.metadata["_providerReasoning"]`，provider 再从这里读取。

---

## 6. 模型目录

模型目录定义位于 [models.py](/Users/admin/PyCharmProject/LiuClaw/ai/models.py)。

### 6.1 查询函数

- `get_model(model_id)`
- `list_models(provider=None)`

### 6.2 当前内置模型

#### OpenAI

- `openai:gpt-5`
- `openai:gpt-5-mini`

#### Anthropic

- `anthropic:claude-sonnet-4`
- `anthropic:claude-haiku-3-5`

#### Zhipu

- `zhipu:glm-5`
- `zhipu:glm-5-turbo`
- `zhipu:glm-4.7`
- `zhipu:glm-4.6`

---

## 7. 对外调用方式

统一入口位于 [client.py](/Users/admin/PyCharmProject/LiuClaw/ai/client.py)。

### 7.1 stream()

```python
async def stream(
    model: Model | str,
    context: Context | dict[str, Any],
    options: Options | None = None,
    *,
    registry: ProviderRegistry | None = None,
) -> StreamSession
```

作用：

- 创建一个流式队列会话 `StreamSession`
- 启动后台 producer task
- provider 产出的统一事件会被持续放入队列

### 7.2 complete()

```python
async def complete(...) -> AssistantMessage
```

作用：

- 内部先调用 `stream()`
- 再持续消费 `StreamSession` 中的事件
- 使用 `StreamAccumulator` 聚合最终 `AssistantMessage`

### 7.3 streamSimple()

简化版流式入口，适合只关心常用参数的场景。

常用参数包括：

- `model`
- `context`
- `reasoning`
- `temperature`
- `max_tokens`
- `timeout`

### 7.4 completeSimple()

简化版一次性调用入口。

---

## 8. StreamSession 队列会话模型

定义位于 [session.py](/Users/admin/PyCharmProject/LiuClaw/ai/session.py)。

`StreamSession` 是上层消费流式事件的核心对象。

```python
session = await stream(...)
```

其内部包含：

- `model`: 当前模型对象
- `queue`: 事件队列
- `producer_task`: 后台生产任务

### 8.1 主要方法

#### consume()

持续从队列取出事件，直到遇到 `done` 或 `error`。

```python
async for event in session.consume():
    ...
```

#### close()

取消 producer task，并等待它结束。

#### wait_closed()

等待 producer 自然结束。

### 8.2 为什么采用队列会话模型

当前设计中：

- provider 仍保持 `async iterator` 输出统一事件
- client 负责桥接为队列
- 上层通过 `StreamSession` 消费

这样做的优点是：

- provider 职责更单一
- 队列背压逻辑集中在 client/session 层
- provider 更容易测试
- 未来若要支持非队列消费模式，不必重写 provider

---

## 9. 一次请求的完整运行流程

当上层调用：

```python
await stream(model, context, options)
```

内部流程如下：

1. 规范化模型
   - `ensure_model()` 把字符串模型 ID 转成 `Model`。

2. 规范化 options
   - `ensure_options()` 保证得到有效 `Options`。
   - `merge_reasoning_metadata()` 把统一 reasoning 映射为 provider 专用参数。

3. 规范化上下文
   - `ensure_context()` 把输入变成统一 `Context`。
   - `sanitize_unicode_context()` 清理危险 Unicode 字符。
   - `convert_context_for_provider()` 做跨 provider 兼容转换。

4. 检查上下文窗口
   - `ensure_context_fits_window()` 做粗略 token 估算和溢出检查。

5. 解析 provider
   - 通过 `ProviderRegistry.resolve()` 按 provider 名或模型前缀找到目标 provider。
   - 注册表支持懒加载和实例缓存。

6. 启动 producer
   - client 创建后台 task。
   - producer 从 provider 的 `async iterator` 读取统一事件。
   - 事件持续写入有界队列。

7. 上层消费事件
   - 上层从 `StreamSession.consume()` 读取事件。
   - 或者 `complete()` 在内部消费并聚合。

可以用一条链表示：

```text
上层业务
  -> ai.stream() / ai.complete()
  -> client
  -> reasoning / converters / unicode / context_window
  -> registry
  -> provider
  -> StreamEvent
  -> StreamSession.queue
  -> 上层消费或 complete() 聚合
```

---

## 10. Provider 注册与懒加载

注册中心位于 [registry.py](/Users/admin/PyCharmProject/LiuClaw/ai/registry.py)。

### 10.1 当前默认工厂

- `openai -> OpenAIProvider`
- `anthropic -> AnthropicProvider`
- `zhipu -> ZhipuProvider`

### 10.2 ProviderRegistry 特性

- 支持已构造实例注册 `register(provider)`
- 支持工厂注册 `register_factory(name, factory)`
- 支持首次 `resolve()` 时懒加载 provider
- 同一 provider 会缓存复用

### 10.3 路由规则

优先顺序如下：

1. 使用 `Model.provider`
2. 如果模型 ID 是 `provider:model_name` 格式，则按前缀取 provider
3. 如果没有 provider 信息，则遍历所有 provider 调用 `supports()` 判断

---

## 11. Provider 抽象与各厂商适配

抽象接口位于 [base.py](/Users/admin/PyCharmProject/LiuClaw/ai/providers/base.py)。

所有 provider 需要实现：

- `supports(model)`
- `stream(model, context, options)`

### 11.1 OpenAIProvider

文件： [openai.py](/Users/admin/PyCharmProject/LiuClaw/ai/providers/openai.py)

职责：

- 读取 `OPENAI_API_KEY`
- 把统一 `Context` 映射为 OpenAI Responses API 请求
- 把 OpenAI 流式事件映射为统一 `StreamEvent`

主要映射：

- `response.output_text.delta -> text_delta`
- `response.reasoning_text.delta -> thinking_delta`
- `response.function_call_arguments.delta -> toolcall_delta`
- `response.function_call_arguments.done -> toolcall_end`

### 11.2 AnthropicProvider

文件： [anthropic.py](/Users/admin/PyCharmProject/LiuClaw/ai/providers/anthropic.py)

职责：

- 读取 `ANTHROPIC_API_KEY`
- 把统一消息与工具映射到 Anthropic Messages API
- 把内容块流映射到统一流式事件

主要映射：

- `content_block_start(text) -> text_start`
- `text_delta -> text_delta`
- `thinking_delta -> thinking_delta`
- `input_json_delta -> toolcall_delta`
- `content_block_stop(tool_use) -> toolcall_end`

### 11.3 ZhipuProvider

文件： [zhipu.py](/Users/admin/PyCharmProject/LiuClaw/ai/providers/zhipu.py)

职责：

- 读取智谱 API Key
- 调用智谱 `chat/completions`
- 解析 SSE 响应
- 把 `reasoning_content`、`content`、`tool_calls` 映射为统一事件

当前支持的认证环境变量：

- `ZHIPU_API_KEY`
- `ZHIPUAI_API_KEY`

可选地址：

- `ZHIPU_BASE_URL`

主要映射：

- `delta.reasoning_content -> thinking_delta`
- `delta.content -> text_delta`
- `delta.tool_calls -> toolcall_delta`
- 流结束后聚合为 `done`

当前实现说明：

- `glm-4.6` 和 `glm-4.7` 在带工具时会默认带上 `tool_stream=True`
- `zhipu` 的价格元数据尚未同步正式价格

---

## 12. 跨 Provider 转换层

文件：

- [messages.py](/Users/admin/PyCharmProject/LiuClaw/ai/converters/messages.py)
- [tools.py](/Users/admin/PyCharmProject/LiuClaw/ai/converters/tools.py)

### 12.1 作用

当目标 provider 和历史消息原始来源不一致时，统一层会在进入 provider 之前做一次语义兼容转换。

当前覆盖范围：

- `Context.messages`
- `Context.tools`

### 12.2 消息转换原则

- `UserMessage` 直接复制
- `ToolResultMessage` 补充 `metadata.targetProvider`
- `AssistantMessage` 补充 `metadata.targetProvider`
- 对带 `thinking` 的历史 assistant 消息，额外记录 `metadata.historicalThinking`

### 12.3 工具转换原则

- 输出统一工具字典
- 保留 `name`、`description`、`inputSchema`
- 在 `metadata` 中记录 `targetProvider`
- 默认标记 `schemaDialect=jsonschema`

---

## 13. utils 子模块说明

### 13.1 streaming.py

文件： [streaming.py](/Users/admin/PyCharmProject/LiuClaw/ai/utils/streaming.py)

提供能力：

- `EventBuilder`: 快速构造统一流式事件。
- `StreamAccumulator`: 聚合 `text_delta`、`thinking_delta`、`toolcall_*`，最终得到 `AssistantMessage`。
- `create_event_queue()`: 创建有界队列。
- `enqueue_event()`: 队列写入。
- `consume_queue()`: 队列消费。
- `drain_queue_to_accumulator()`: 从队列直接聚合最终消息。
- `forward_stream_to_queue()`: 把 provider 事件流桥接到队列。
- `finalize_producer_error()`: producer 出错时向队列补发 `error` 事件。
- `cancel_producer_task()`: 取消 producer 并做错误收尾。
- `create_done_event()`: 构造统一 `done` 事件。

### 13.2 context_window.py

文件： [context_window.py](/Users/admin/PyCharmProject/LiuClaw/ai/utils/context_window.py)

提供能力：

- `estimate_context_tokens(context)`: 粗略估算 token。
- `detect_context_overflow(model, context, options)`: 返回窗口检测报告。
- `ensure_context_fits_window(...)`: 溢出时抛错。

当前策略：

- 只检测并报错
- 不自动裁剪上下文

### 13.3 schema_validation.py

文件： [schema_validation.py](/Users/admin/PyCharmProject/LiuClaw/ai/utils/schema_validation.py)

提供能力：

- `validate_tool_arguments(tool, arguments)`

当前实现是 Python 内部的 JSON Schema 等价校验，不依赖 Node/AJV 运行时。

当前覆盖的 schema 类型包括：

- `object`
- `array`
- `string`
- `integer`
- `number`
- `boolean`
- `null`

### 13.4 unicode.py

文件： [unicode.py](/Users/admin/PyCharmProject/LiuClaw/ai/utils/unicode.py)

提供能力：

- `sanitize_unicode(text)`
- `sanitize_unicode_context(context)`

处理原则：

- 使用 `NFKC` 做 Unicode 规范化
- 去掉危险控制字符和零宽控制类字符
- 保留 `\n`、`\r`、`\t`

---

## 14. 错误体系

异常定义位于 [errors.py](/Users/admin/PyCharmProject/LiuClaw/ai/errors.py)。

### 14.1 AIError

统一基类。

### 14.2 ProviderNotFoundError

当模型找不到可用 provider 时抛出。

### 14.3 AuthenticationError

当 provider API Key 缺失或无效时抛出。

### 14.4 UnsupportedFeatureError

当某 provider 不支持特定功能，例如 reasoning 映射时抛出。

### 14.5 ProviderResponseError

当 provider SDK 调用失败、协议不合法、流式解析失败时抛出。

---

## 15. 常见调用示例

### 15.1 一次性调用

```python
from ai import Context, UserMessage, complete

message = await complete(
    model="openai:gpt-5",
    context=Context(
        systemPrompt="你是一个可靠的助手",
        messages=[UserMessage(content="请总结下面内容")],
        tools=[],
    ),
)

print(message.content)
```

### 15.2 流式调用

```python
from ai import Context, UserMessage, stream

session = await stream(
    model="anthropic:claude-sonnet-4",
    context=Context(
        systemPrompt="你是一个可靠的助手",
        messages=[UserMessage(content="帮我写一个 Python 函数")],
        tools=[],
    ),
)

async for event in session.consume():
    if event.type == "text_delta" and event.text:
        print(event.text, end="")
    if event.type in {"done", "error"}:
        break
```

### 15.3 带工具调用

```python
from ai import Context, Tool, UserMessage, complete
from ai.options import Options

message = await complete(
    model="zhipu:glm-4.7",
    context=Context(
        systemPrompt="你是一个可以调用工具的助手",
        messages=[UserMessage(content="帮我查一下上海天气")],
        tools=[
            Tool(
                name="lookup_weather",
                description="查询城市天气",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "city": {"type": "string"}
                    },
                    "required": ["city"],
                },
            )
        ],
    ),
    options=Options(reasoning="high"),
)

for tool_call in message.toolCalls:
    print(tool_call.name, tool_call.arguments)
```

---

## 16. 上层接入建议

如果这个模块用于上层业务系统，建议采用以下接入方式：

### 16.1 统一由业务层组装 Context

业务层只负责：

- 组装 `systemPrompt`
- 组装 `messages`
- 注入当前可用 `tools`

### 16.2 流式场景统一消费 StreamSession

推荐流程：

1. 调 `stream()`
2. 监听 `text_delta`，推送到前端
3. 监听 `toolcall_*`，做工具执行编排
4. 遇到 `done` 取最终 `assistantMessage`
5. 遇到 `error` 做统一错误处理

### 16.3 一次性场景统一走 complete()

如果不需要逐步消费事件，直接用 `complete()` 即可。

### 16.4 不要让业务层直接依赖 provider SDK

业务层应只依赖：

- `Context`
- `Message` 类型族
- `Tool`
- `Options`
- `StreamSession`
- `StreamEvent`

不要直接依赖：

- OpenAI 原始事件名
- Anthropic 原始 block 类型
- Zhipu 原始 SSE chunk 结构

---

## 17. 扩展新 Provider 的方式

新增 provider 时，建议按下面步骤实现：

1. 新建 `ai/providers/<provider>.py`
2. 继承 `Provider`
3. 实现 `supports()` 和 `stream()`
4. 在 `registry._default_factories()` 注册默认工厂
5. 在 `models.py` 中加入内置模型目录
6. 在 `reasoning.py` 中补充该 provider 的 reasoning 映射
7. 如有需要，在 `converters/` 中补充兼容转换
8. 为新 provider 增加协议级测试

实现边界建议保持如下：

- provider 负责请求装配和事件映射
- client 负责队列桥接和最终聚合
- utils 负责可复用基础设施
- registry 负责实例化和路由

---

## 18. 当前实现边界与注意事项

### 18.1 当前支持重点

当前版本优先支持：

- 文本消息
- thinking / reasoning
- function tool calling
- 流式统一事件
- 队列式消费

### 18.2 当前未重点覆盖

当前版本未优先实现：

- 图片、音频、文件上传等多模态能力
- sync 风格公共接口
- provider 专属高级工具类型统一抽象
- 自动上下文裁剪

### 18.3 关于 zhipu 价格字段

`zhipu` 相关模型目前只完成了功能接入，价格字段尚未完成正式同步，因此：

- `inputPrice = 0.0`
- `outputPrice = 0.0`
- `metadata.priceStatus = "needs_manual_sync"`

如果上层需要基于价格做计费或路由，需要先补正式价格数据。

---

## 19. 总结

`ai` 模块当前已经形成一套相对完整的统一接入层：

- 上层通过 `Context + Model + Options` 发起调用
- provider 差异通过适配层吸收
- 流式协议通过 `StreamEvent` 统一
- 流式消费通过 `StreamSession` 队列模型统一
- 一次性调用通过 `complete()` 聚合同一条流式链路
- reasoning、消息兼容、工具 schema、上下文窗口、Unicode 清理均有独立基础设施支撑

对于上层系统来说，接入这个模块后，基本只需要理解以下几个核心对象：

- `Context`
- `UserMessage / AssistantMessage / ToolResultMessage`
- `Tool`
- `Model`
- `Options`
- `StreamSession`
- `StreamEvent`

这也是当前 `ai` 模块最核心的设计目标。
