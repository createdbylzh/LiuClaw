# agent_core 模块文档

## 1. 模块概述

`agent_core` 是建立在 [`ai`](/Users/admin/PyCharmProject/LiuClaw/ai) 模块之上的 Agent 运行时层，目标是把“模型调用 + 工具调用 + 多轮循环 + 事件流通知 + 高层状态管理”组织成一套统一 API。

它主要解决四类问题：

1. 管理 Agent 运行状态。
2. 执行 Agent 主循环。
3. 以统一事件流向 UI 或上层应用暴露运行过程。
4. 同时提供低层循环 API 和高层面向业务的 `Agent` API。

当前模块由 3 个核心文件组成：

- [`types.py`](/Users/admin/PyCharmProject/LiuClaw/agent_core/types.py)：定义核心协议、状态、事件、工具与配置。
- [`agent_loop.py`](/Users/admin/PyCharmProject/LiuClaw/agent_core/agent_loop.py)：实现低层 Agent 主循环。
- [`agent.py`](/Users/admin/PyCharmProject/LiuClaw/agent_core/agent.py)：实现高层 `Agent` 运行时封装。

模块公开导出定义在 [`__init__.py`](/Users/admin/PyCharmProject/LiuClaw/agent_core/__init__.py) 中。

---

## 2. 整体分层

### 2.1 `types.py`

这一层只保留最核心的协议与数据模型，尽量不掺杂运行实现细节。它定义了：

- 流式函数类型 `AgentStreamFn`
- 工具执行模式 `ToolExecutionMode`
- 工具安检/质检上下文与返回结果
- `AgentTool`
- `AgentContext`
- `AgentLoopConfig`
- `AgentState`
- `AgentEventType`
- `AgentEvent`

这层的职责是“约定形状”，而不是“执行逻辑”。

### 2.2 `agent_loop.py`

这一层是低层运行时核心，主要负责：

- 启动一轮或续跑一轮 Agent 循环
- 打开底层 LLM 流式会话
- 将 `ai` 模块的流式事件映射成 `AgentEvent`
- 执行工具调用
- 处理 steering 和 follow-up
- 维护低层状态并推送事件到 `StreamSession[AgentEvent]`

这层更接近运行引擎。

### 2.3 `agent.py`

这一层面向应用开发，负责：

- 管理高层状态对象
- 暴露普通消息、steering、follow-up 三类显式消息队列
- 管理监听器
- 统一处理取消、等待、重置
- 对低层 session 做桥接，保证外部拿到的事件已经过高层状态同步

这层更接近业务入口。

---

## 3. 公开 API 一览

当前 `agent_core` 对外公开这些主要对象：

- `Agent`
- `AgentOptions`
- `agentLoop`
- `agentLoopContinue`
- `AgentLoopConfig`
- `AgentState`
- `AgentContext`
- `AgentEvent`
- `AgentEventType`
- `AgentTool`
- `AgentStreamFn`
- `ToolExecutionMode`
- `BeforeToolCallContext`
- `BeforeToolCallAllow`
- `BeforeToolCallSkip`
- `BeforeToolCallError`
- `BeforeToolCallResult`
- `AfterToolCallContext`
- `AfterToolCallPass`
- `AfterToolCallReplace`
- `AfterToolCallResult`

---

## 4. 核心类型说明

## 4.1 `AgentContext`

`AgentContext` 表示一次 Agent 调用 LLM 或工具时的上下文快照，包含：

- `systemPrompt`
- `history`
- `tools`

它是一个“只关注当前轮上下文”的轻量对象，主要用于：

- 传给底层流式函数
- 传给工具执行器
- 传给 `beforeToolCall` / `afterToolCall`

## 4.2 `AgentStreamFn`

`AgentStreamFn` 定义了“调用 AI 的函数”应该具备的统一签名：

```python
async def __call__(
    model: Model | str,
    context: AgentContext,
    thinking: ReasoningLevel | None,
    registry: ProviderRegistry | None = None,
) -> StreamSession:
    ...
```

语义如下：

- `model`：当前模型
- `context`：当前上下文
- `thinking`：思考级别
- `registry`：可选 provider 注册表
- 返回值：`StreamSession`

当前默认实现不是直接把复杂的 provider 协议暴露出来，而是通过 [`agent_loop.py`](/Users/admin/PyCharmProject/LiuClaw/agent_core/agent_loop.py) 内部的 `_default_stream()` 适配到 `ai.streamSimple(...)`。

也就是说：

- 不传自定义 `stream` 时，默认走 `ai.streamSimple`
- 传了自定义 `stream` 时，优先使用自定义实现

## 4.3 `AgentTool`

`AgentTool` 继承自 `ai.types.Tool`，在静态工具定义基础上增加了一个执行器：

- `execute(arguments, context)`

其中：

- `arguments` 是字符串形式的参数
- `context` 是 `AgentContext`

执行结果可以是：

- `str`
- `dict`
- `ToolResultMessage`

最终都会在低层被归一化为 `ToolResultMessage`。

## 4.4 工具执行模式

`ToolExecutionMode` 目前支持两种取值：

- `"serial"`：串行执行
- `"parallel"`：并行执行

当前默认是串行模式。

### 串行模式

特点：

- 按 assistant 返回的 `toolCalls` 顺序逐个执行
- 事件顺序更稳定
- 更容易调试

### 并行模式

特点：

- 同一轮中的多个工具调用会并发执行
- 工具结果回填到上下文时，仍按原始 `toolCalls` 顺序整理结果
- 更适合多个互不依赖的工具调用

## 4.5 `beforeToolCall` 与 `afterToolCall`

`beforeToolCall` 用于执行前安检，`afterToolCall` 用于执行后质检。

### `BeforeToolCallContext`

包含：

- `state`
- `tool`
- `toolCall`
- `arguments`
- `agentContext`

### `BeforeToolCallResult`

可以返回：

- `BeforeToolCallAllow`
- `BeforeToolCallSkip`
- `BeforeToolCallError`
- `None`

语义分别是：

- `allow`：允许真实执行
- `skip`：跳过真实执行，直接使用替代结果
- `error`：阻止执行，并生成错误结果
- `None`：等同于允许执行

### `AfterToolCallContext`

包含：

- `state`
- `tool`
- `toolCall`
- `arguments`
- `result`
- `agentContext`

### `AfterToolCallResult`

可以返回：

- `AfterToolCallPass`
- `AfterToolCallReplace`
- `None`

语义分别是：

- `pass`：保留原结果
- `replace`：使用替代结果覆盖原结果
- `None`：等同于保留原结果

## 4.6 `AgentLoopConfig`

`AgentLoopConfig` 是低层循环配置对象，定义了 Agent loop 运行所需的一切：

- `systemPrompt`
- `model`
- `thinking`
- `tools`
- `stream`
- `steer`
- `followUp`
- `toolExecutionMode`
- `beforeToolCall`
- `afterToolCall`
- `registry`

它的定位是：

- 描述这轮 Agent loop 用什么模型、什么工具、什么控制逻辑来运行

## 4.7 `AgentState`

`AgentState` 描述 Agent 运行中的实时状态，包含：

- `systemPrompt`
- `model`
- `thinking`
- `tools`
- `history`
- `isStreaming`
- `currentMessage`
- `runningToolCall`
- `error`

几个关键字段说明：

- `history`：完整对话历史
- `isStreaming`：当前是否正在流式接收 assistant 输出
- `currentMessage`：当前正在生成的 assistant 消息
- `runningToolCall`：当前正在执行的工具调用
- `error`：最近一次运行错误

## 4.8 事件模型

`AgentEventType` 当前固定为 10 类事件：

- `agent_start`
- `agent_end`
- `turn_start`
- `turn_end`
- `message_start`
- `message_update`
- `message_end`
- `tool_execution_start`
- `tool_execution_update`
- `tool_execution_end`

`AgentEvent` 中包含这些主要字段：

- `type`
- `state`
- `message`
- `messageDelta`
- `toolCall`
- `toolResult`
- `error`

事件对象的作用是：

- 向 UI 推送统一生命周期信号
- 让外部订阅者获得运行态快照
- 把 assistant 输出、工具执行和对话轮次用统一协议串起来

---

## 5. 低层主循环设计

低层循环代码位于 [`agent_loop.py`](/Users/admin/PyCharmProject/LiuClaw/agent_core/agent_loop.py)。

它的核心入口有两个：

- `agentLoop(...)`
- `agentLoopContinue(...)`

此外，还有几个重要内部函数：

- `runAgentLoop(...)`
- `runLoop(...)`
- `streamAssistantResponse(...)`
- `executeToolCalls(...)`
- `executeToolCallsSequential(...)`
- `executeToolCallsParallel(...)`
- `prepareToolCall(...)`
- `executePreparedToolCall(...)`
- `finalizeExecutedToolCall(...)`
- `emitToolCallOutcome(...)`

## 5.1 `agentLoop()`

作用：

- 启动新对话

行为：

1. 根据 `AgentLoopConfig` 构造初始 `AgentState`
2. 创建 `StreamSession[AgentEvent]`
3. 后台启动 `runAgentLoop(...)`
4. 立即返回 session

这意味着调用方不需要等整个循环跑完，就可以立刻开始订阅事件。

示例：

```python
session = await agentLoop(loop_config, initialMessages=[UserMessage(content="你好")])
async for event in session.consume():
    print(event.type)
```

## 5.2 `agentLoopContinue()`

作用：

- 从已有状态继续运行，不额外添加新消息

约束：

- `state.history` 不能为空
- `history` 最后一条不能是 `AssistantMessage`

这是为了保证“继续”发生在合法的上下文位置上，例如：

- 上一轮停在用户消息后
- 上一轮停在工具结果后

而不是 assistant 已经刚刚说完又立刻继续。

## 5.3 `runAgentLoop()`

这是后台生产者入口，负责：

1. 记录本轮新增消息
2. 发出 `agent_start`
3. 发出首轮 `turn_start`
4. 把新增用户消息写入历史并发出消息事件
5. 调用 `runLoop(...)`

注意：

- 这里通过 queue 推送事件，而不是直接 `yield`
- 这也是为什么外层可以用 `StreamSession` 做统一消费

## 5.4 `runLoop()`

这是主循环核心。

当前实现大体上是“两层循环”：

- 内层负责 pending 消息、assistant 回复、工具执行、steering
- 外层负责 follow-up

执行流程可以概括为：

1. 先检查一次 `steer()`
2. 进入内层循环
3. 必要时发 `turn_start`
4. 把 `pendingMessages` 追加到历史，并发出对应的消息事件
5. 调用 `streamAssistantResponse(...)`
6. 如果 assistant 带有工具调用，则执行 `executeToolCalls(...)`
7. 发 `turn_end`
8. 再检查一次 `steer()`
9. 如果有 steering 消息，则继续内层下一轮
10. 没有 steering 时，检查 `followUp()`
11. 如果有 follow-up 消息，则进入外层下一轮
12. 否则发 `agent_end`

### 当前 steering 时序说明

这里有一个当前实现细节需要特别注意：

- `runLoop()` 在真正进入主循环前，会先检查一次 `steer()`

因此，如果在启动前就已经准备好了 steering 消息，那么这些消息会在首轮 assistant 调用前就进入上下文。

这和“严格只在 `turn_end` 之后触发 steering”略有不同。文档这里按当前代码真实行为说明。

## 5.5 `streamAssistantResponse()`

作用：

- 获取单轮 assistant 回复
- 把底层 `ai` 流式事件映射成公开 `AgentEvent`

内部主要步骤：

1. 通过 `_open_stream()` 获取流式 session
2. 将 `state.isStreaming = True`
3. 初始化 `state.currentMessage`
4. 消费底层 `StreamEvent`
5. 把底层事件转换成 `message_start` / `message_update` / `message_end`
6. 将最终 assistant 消息追加到历史
7. 流结束后把 `state.isStreaming = False`

### 事件映射规则

当前实现中：

- `start`：首次触发 `message_start`
- `text_delta` / `thinking_delta` / `toolcall_delta` 等中间增量：触发 `message_update`
- `done`：写入最终 assistant 消息并触发 `message_end`
- `error`：设置 `state.error`，返回 `None`

### 纯 tool-call assistant 场景

如果模型只产出工具调用、没有文本内容：

- 仍然会补出一组 assistant 消息生命周期事件
- 这样 UI 层依然能把它视作一条完整 assistant 消息

## 5.6 工具执行流程

工具执行入口是 `executeToolCalls(...)`。

它会先读取 assistant 消息中的 `toolCalls`，再根据 `loop.toolExecutionMode` 选择：

- `executeToolCallsSequential(...)`
- `executeToolCallsParallel(...)`

### 5.6.1 `prepareToolCall()`

准备阶段负责四件事：

1. 查找工具
2. 解析参数
3. 校验参数 schema
4. 调用 `beforeToolCall`

如果失败，会返回 `PreparedToolCallError`；
如果成功，会返回 `PreparedToolCall`。

### 5.6.2 `executePreparedToolCall()`

负责真实执行工具：

- 设置 `state.runningToolCall`
- 发出 `tool_execution_update`
- 调用工具的 `execute(...)`
- 完成后清理 `state.runningToolCall`

### 5.6.3 `finalizeExecutedToolCall()`

负责工具执行后处理：

1. 把执行结果归一化成 `ToolResultMessage`
2. 调用 `afterToolCall`
3. 若需要则替换结果
4. 最终交给 `emitToolCallOutcome(...)`

### 5.6.4 `emitToolCallOutcome()`

这是工具结果落盘的统一出口，负责：

1. 发 `tool_execution_end`
2. 生成工具结果消息
3. 追加到 `state.history`
4. 再为工具结果补发一组 `message_start` / `message_end`

这使得工具结果在上下文中的表现方式与普通消息一致，便于下一轮模型继续消费。

### 5.6.5 工具错误策略

当前默认策略是：

- 工具不存在：不会终止 Agent，生成错误型 `ToolResultMessage`
- 参数解析失败：不会终止 Agent，生成错误型 `ToolResultMessage`
- schema 校验失败：不会终止 Agent，生成错误型 `ToolResultMessage`
- `beforeToolCall` 阻止执行：不会终止 Agent，生成错误型结果
- 工具执行异常：当前实现依赖上层异常路径处理，应在使用工具时保证执行器本身尽量可控

错误型工具结果会写入：

- `content = 错误文本`
- `metadata["error"] = True`

---

## 6. 高层 `Agent` 设计

高层封装位于 [`agent.py`](/Users/admin/PyCharmProject/LiuClaw/agent_core/agent.py)。

它的定位不是简单透传底层 session，而是一个真正的高层运行时对象。

## 6.1 `AgentOptions`

`AgentOptions` 是高层构造配置，包含：

- `loop`
- `initialState`
- `listeners`
- `pendingMessages`
- `steeringMessages`
- `followUpMessages`
- `autoCopyState`

说明如下：

- `loop`：底层循环配置来源
- `initialState`：允许从已有状态恢复
- `listeners`：初始监听器列表
- `pendingMessages`：高层普通输入队列初始值
- `steeringMessages`：高层 steering 队列初始值
- `followUpMessages`：高层 follow-up 队列初始值
- `autoCopyState`：是否在构造时复制输入状态，避免共享引用

## 6.2 高层三类消息队列

当前高层 `Agent` 已显式区分三类消息队列。

### 普通待处理消息队列

用途：

- 存放用户刚提交、准备进入下一次运行的新消息

相关 API：

- `enqueue(...)`
- `dequeueAll()`
- `clearQueue()`
- `queueSize()`
- `pendingMessages`

### steering 队列

用途：

- 存放中途插话消息
- 会在高层桥接成底层 `steer()`

相关 API：

- `enqueueSteering(...)`
- `dequeueSteeringAll()`
- `clearSteeringQueue()`
- `steeringQueueSize()`
- `steeringMessages`

### follow-up 队列

用途：

- 存放当前任务自然结束后再处理的消息
- 会在高层桥接成底层 `followUp()`

相关 API：

- `enqueueFollowUp(...)`
- `dequeueFollowUpAll()`
- `clearFollowUpQueue()`
- `followUpQueueSize()`
- `followUpMessages`

## 6.3 高层如何桥接 steering / follow-up

`Agent._buildLoopConfig()` 不会简单把原始 `_loop.steer` 和 `_loop.followUp` 原样下传，而是会包装成两个高层桥接函数：

- 先读取高层显式队列中的消息
- 再调用外部传入的 `steer` / `followUp` hook
- 把两部分结果合并后返回给底层 loop

这意味着：

- 高层显式队列和低层 hook 机制是同时生效的
- 业务层既可以调用 `enqueueSteering(...)`
- 也可以直接在 `AgentLoopConfig.steer` 中写自定义逻辑

## 6.4 监听器系统

高层支持事件监听器订阅。

相关 API：

- `subscribe(listener)`
- `unsubscribe(listener)`
- `clearListeners()`

监听器特点：

- 按注册顺序调用
- 支持 sync / async
- 单个监听器报错不会打断主流程
- 监听器错误会写入 `state.error`

## 6.5 状态管理

高层支持读取和修改状态。

相关 API：

- `getState()`
- `setState(state)`
- `updateState(**kwargs)`
- `setThinking(...)`
- `setSystemPrompt(...)`
- `setModel(...)`
- `setTools(...)`

注意：

- 运行中不允许随意修改关键运行字段
- `setState()` 在运行中会直接报错
- `updateState()` 在运行中修改 `isStreaming`、`currentMessage`、`runningToolCall` 会报错

## 6.6 运行控制

高层提供：

- `cancel()`
- `wait()`
- `reset()`

### `cancel()`

作用：

- 取消当前运行中的高层/底层 session
- 不会清空历史消息

### `wait()`

作用：

- 等待当前 session 的后台任务结束
- 不主动消费事件

### `reset()`

作用：

- 清空三类高层消息队列
- 清空当前 session / task
- 重建初始状态

限制：

- 运行中禁止 `reset()`

## 6.7 高层入口方法

### `prompt(message)`

作用：

- 先入普通消息队列，再立即启动运行

### `continueConversation()`

作用：

- 从当前状态继续运行
- 不添加新消息

### `resume()`

作用：

- `continueConversation()` 的兼容别名

### `run()`

作用：

- 如果普通消息队列非空，则消费这些消息并启动运行
- 如果普通消息队列为空，则尝试按“继续”模式运行

---

## 7. 高层桥接会话模型

高层 `Agent` 当前不是直接把底层 session 原样返回，而是采用“双 session 桥接”模型：

1. 底层 session：来自 `agentLoop(...)` 或 `agentLoopContinue(...)`
2. 高层 session：暴露给调用方
3. 中间桥接任务：消费底层事件，调用 `_handleLoopEvent(...)` 更新本地状态，再转发到高层 queue

这样设计的好处是：

- 高层状态始终和外部看到的事件保持同步
- 监听器拿到的是“已经过高层状态同步”的事件
- 高层可以统一管理取消、等待和清理

---

## 8. 典型使用方式

## 8.1 低层 API 用法

```python
from ai import UserMessage
from agent_core import AgentLoopConfig, agentLoop

loop = AgentLoopConfig(
    model="openai:gpt-5.4",
)

session = await agentLoop(loop, initialMessages=[UserMessage(content="你好")])

async for event in session.consume():
    print(event.type, event.messageDelta)
```

适合场景：

- 需要完全控制 loop 行为
- 自己接管状态和事件处理
- 做底层框架或中间层

## 8.2 高层 `Agent` 用法

```python
from ai import UserMessage
from agent_core import Agent, AgentLoopConfig

agent = Agent(
    AgentLoopConfig(
        model="openai:gpt-5.4",
    )
)

session = await agent.prompt(UserMessage(content="帮我总结这个需求"))

async for event in session.consume():
    print(event.type)

print(agent.lastMessage)
```

适合场景：

- 需要一个可复用 Agent 对象
- 需要保留状态
- 需要监听器、取消、等待、重置
- 需要显式管理普通消息、steering、follow-up 三类队列

## 8.3 高层 steering / follow-up 用法

```python
from ai import UserMessage

agent.enqueue(UserMessage(content="先处理主任务"))
agent.enqueueSteering(UserMessage(content="中途补充一个限制条件"))
agent.enqueueFollowUp(UserMessage(content="任务结束后再做总结"))

session = await agent.run()
async for event in session.consume():
    ...
```

---

## 9. 事件生命周期说明

一次较完整的运行中，常见事件顺序大致如下：

1. `agent_start`
2. `turn_start`
3. 用户消息对应的 `message_start`
4. 用户消息对应的 `message_end`
5. assistant 的 `message_start`
6. assistant 的若干 `message_update`
7. assistant 的 `message_end`
8. 如有工具调用：
9. `tool_execution_start`
10. `tool_execution_update`
11. `tool_execution_end`
12. 工具结果对应的 `message_start`
13. 工具结果对应的 `message_end`
14. `turn_end`
15. 若 steering / follow-up 触发，则继续下一轮
16. `agent_end`

需要注意：

- `message_*` 不只会出现在用户和 assistant 上，也会用于工具结果消息
- `tool_execution_*` 只描述工具执行生命周期
- `agent_end` 是整个 session 的终止标记

---

## 10. 与 `ai` 模块的关系

`agent_core` 并不重新实现 provider 层协议，而是复用 `ai` 提供的基础能力：

- 复用 `ai.types` 中的消息模型和模型类型
- 复用 `ai.streamSimple(...)`
- 复用泛型化后的 `ai.session.StreamSession`
- 复用参数 schema 校验工具 `validate_tool_arguments(...)`

也就是说：

- `agent_core` 关心的是 Agent 运行时编排
- `ai` 关心的是模型、provider 和底层流式协议

两者职责边界比较清晰。

---

## 11. 当前实现中的几个重要细节

## 11.1 默认流式入口是 `streamSimple`

当前默认底层调用走 `ai.streamSimple(...)`，而不是在 `types.py` 中暴露更复杂的 mode 配置。

这让 `AgentLoopConfig` 更简单，也更符合当前 Agent runtime 的默认使用方式。

## 11.2 `StreamSession` 已泛型化

`ai.session.StreamSession` 现在是泛型的：

- `StreamSession[StreamEvent]` 可用于 `ai`
- `StreamSession[AgentEvent]` 可用于 `agent_core`

运行时行为不变，仍然保留：

- `queue`
- `consume()`
- `close()`
- `wait_closed()`

## 11.3 高层 `run()` 与 `continueConversation()` 的区别

- `run()`：优先处理高层普通消息队列
- `continueConversation()`：纯续跑，不添加新消息

如果当前没有历史，直接 `continueConversation()` 会报错。

## 11.4 `agentLoopContinue()` 的合法性检查

低层继续运行时有两个显式校验：

- `history` 不能为空
- 最后一条消息不能是 assistant

这是为了避免在非法断点上继续执行。

## 11.5 事件中的 `state` 是快照

底层每次发事件时，都会对状态做一次快照复制，而不是直接把原始可变状态对象暴露出去。

这样可以避免：

- UI 持有事件后又被后续运行污染
- 调试时出现“同一个事件对象状态被后续修改”的问题

---

## 12. 适用场景建议

推荐使用低层 `agentLoop` 的场景：

- 你正在做框架层或基础设施层封装
- 你想完全掌控循环行为
- 你不需要高层 Agent 对象长期持有状态

推荐使用高层 `Agent` 的场景：

- 你在做应用层开发
- 你需要反复与同一个 Agent 交互
- 你需要显式消息队列和事件监听
- 你需要取消、等待和重置能力

---

## 13. 后续可继续演进的方向

从当前实现看，后续还可以继续加强这些方向：

1. 更细粒度的工具异常分类与恢复策略。
2. 更严格的 steering 时机控制。
3. 对工具执行超时、并发上限、取消传播的增强支持。
4. 更多与 UI 直接对应的事件元数据。
5. README 与示例代码进一步同步到当前高层三队列设计。

---

## 14. 总结

`agent_core` 当前已经形成了一套较完整的 Agent runtime 结构：

- `types.py` 定协议
- `agent_loop.py` 跑循环
- `agent.py` 做高层封装

它既能支持底层可控的事件流运行，也能支持高层可复用的 `Agent` 对象式开发。

尤其是当前高层已经显式区分了：

- 普通输入队列
- steering 队列
- follow-up 队列

这让整个模块在语义上更贴近真实 Agent 场景，也更方便后续继续扩展。
