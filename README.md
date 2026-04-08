# LiuClaw

LiuClaw 是一个分层清晰的智能体项目，既包含面向终端的编码助手，也包含面向聊天平台的机器人运行壳。当前核心由四部分组成：

- `ai`：统一大模型接入层，负责模型协议、provider 适配、流式事件、上下文预处理与工具参数兼容。
- `agent_core`：Agent 运行时内核，负责多轮循环、工具调用、状态管理、事件流、中断与重试。
- `coding_agent`：产品编排层，负责 CLI、TUI、会话持久化、工具注册、资源加载、扩展机制与上下文压缩。
- `mom`：聊天平台适配与运行编排层，负责飞书事件接入、频道上下文维护、Agent 会话衔接、消息回写与事件驱动任务。

如果把整个仓库看成一条运行链路，可以理解为：

`coding_agent` 负责把终端应用装起来，`mom` 负责把聊天机器人装起来，`agent_core` 负责把 Agent 跑起来，`ai` 负责把模型调起来。

## 项目结构

```text
LiuClaw/
├── ai/                  # 统一 LLM 接入层
├── agent_core/          # Agent 运行时内核
├── coding_agent/        # 终端产品层与交互入口
├── mom/                 # 飞书机器人适配层与运行壳
├── tests/               # 模块级行为测试
├── examples/            # 基础调用示例
├── pyproject.toml
└── README.md
```

## 分层说明

### 1. `ai`

`ai` 模块把不同厂商的大模型能力统一成一致接口，核心能力包括：

- 统一类型体系：`Context`、`Model`、`AssistantMessage`、`ToolCall`、`StreamEvent`
- 统一调用入口：`stream()`、`complete()`、`streamSimple()`、`completeSimple()`
- provider 注册与懒加载：`ProviderRegistry`
- 模型目录与配置覆盖：`ModelRegistry`、`AIConfig`
- provider 前转换与清理：messages/tools/thinking/capabilities/context-window/unicode
- 统一流式聚合与错误模型

更详细说明见 [ai/ai模块.md](/Users/admin/PyCharmProject/LiuClaw/ai/ai模块.md)。

### 2. `agent_core`

`agent_core` 建立在 `ai` 之上，负责把“模型输出 + 工具执行 + 多轮会话”组织成可持续推进的 Agent 循环，核心能力包括：

- 低层循环入口：`agentLoop()`、`agentLoopContinue()`
- 高层封装：`Agent`
- 状态模型：`AgentState`、`AgentRuntimeFlags`
- 统一事件：`AgentEvent`
- 工具前后钩子：`beforeToolCall`、`afterToolCall`
- steering / follow-up / retry / abort 等运行控制

更详细说明见 [agent_core/agent-core模块.md](/Users/admin/PyCharmProject/LiuClaw/agent_core/agent-core模块.md)。

### 3. `coding_agent`

`coding_agent` 是面向终端使用的产品层。它把模型、工具、系统提示、会话存储、扩展与交互界面组装成一个真正可运行的编码助手，核心能力包括：

- CLI 入口与 one-shot / interactive 两种模式
- 用户级与项目级配置加载
- 资源加载：skills、prompts、themes、`AGENTS.md`、extensions
- `AgentSession` 会话编排与事件映射
- 工具注册与安全策略
- session 持久化、恢复与分支摘要压缩
- 基于 `prompt_toolkit` 的交互界面

更详细说明见 [coding_agent/coding-agent模块.md](/Users/admin/PyCharmProject/LiuClaw/coding_agent/coding-agent模块.md)。

### 4. `mom`

`mom` 是面向聊天平台的产品编排层，当前主要适配飞书。它把聊天消息、附件、频道记忆、系统事件和底层 Agent 会话组织成一个可持续运行的团队协作机器人，核心能力包括：

- 飞书 webhook / long connection 双模式接入
- 群聊 @ 触发、私聊自动触发
- 频道级日志、记忆、附件和 scratch 目录管理
- 历史聊天同步到 Agent session，保证多轮上下文连续
- 默认只输出最终答复，按需打开中间态、思考与工具细节
- `immediate`、`one-shot`、`periodic` 三类本地事件驱动
- stop 中断、频道内串行、系统事件排队执行

更详细说明见 [mom/mom模块.md](/Users/admin/PyCharmProject/LiuClaw/mom/mom模块.md)。

## 快速开始

### 安装依赖

```bash
uv sync
```

### 运行测试

```bash
uv run pytest
```

### 运行交互式编码助手

```bash
uv run python -m coding_agent
```

常用参数：

- `--model`：指定模型 ID
- `--cwd`：指定工作目录
- `--thinking`：`low`、`medium`、`high`
- `--session`：恢复历史会话
- `--new`：强制新建会话
- `--compact`：压缩当前会话后退出
- `--theme`：指定主题

### 单次提示模式

```bash
uv run python -m coding_agent "帮我总结当前项目结构"
```

### 运行 mom 飞书机器人

最小启动方式如下：

```bash
MOM_WORKDIR=/absolute/workspace \
MOM_FEISHU_APP_ID=cli_xxx \
MOM_FEISHU_APP_SECRET=xxx \
uv run python -m mom
```

行为约定：

- 私聊消息默认触发机器人处理。
- 群聊消息只有在 `@mom` 这类 mention 场景下才会触发。
- 同一频道内默认串行执行；如果上一条任务还在运行，新的普通消息不会并发挤进同一个 Agent 会话。
- 用户可发送 `stop` 中断当前频道正在执行的任务。

常用环境变量：

- `MOM_WORKDIR`：mom 工作区根目录，也是 `.mom/` 数据目录所在位置
- `MOM_FEISHU_APP_ID`：飞书应用 App ID
- `MOM_FEISHU_APP_SECRET`：飞书应用密钥
- `MOM_FEISHU_CONNECTION_MODE`：连接模式，默认 `long_connection`，也可设为 `webhook`
- `MOM_FEISHU_VERIFICATION_TOKEN`：webhook 校验 token
- `MOM_FEISHU_ENCRYPT_KEY`：飞书事件加密 key
- `MOM_BIND_HOST` / `MOM_BIND_PORT`：webhook 模式的监听地址与端口
- `MOM_MODEL`：指定 mom 使用的模型 ID
- `MOM_RENDER_MODE`：输出模式，默认 `final_only`
- `MOM_PLACEHOLDER_TEXT`：处理中占位文案
- `MOM_SHOW_INTERMEDIATE_UPDATES`：是否显示流式中间更新
- `MOM_SHOW_TOOL_DETAILS`：是否显示工具调用详情
- `MOM_SHOW_THINKING`：是否显示思考内容

如果使用长连接模式，需要额外安装飞书 SDK：

```bash
uv add lark-oapi
```

mom 的核心处理链路如下：

1. 飞书事件进入 `FeishuBotTransport`。
2. 原始事件被解析为统一的 `ChatEvent`。
3. 用户消息写入频道 `log.jsonl`。
4. `MomApp` 判断是否触发、是否去重、是否需要排队。
5. 历史聊天从 `log.jsonl` 同步到 Agent session。
6. 当前频道上下文、目录约定和记忆被拼进系统提示词。
7. `MomRunner` 驱动一次 Agent turn。
8. 最终结果回写到飞书，并记录到频道日志。

mom 启动后会在工作区下维护 `.mom/` 目录，典型结构如下：

```text
.mom/
├── settings.json
├── channel_index.json
├── events/
├── sessions/
└── channels/
    └── <chat_id>/
        ├── log.jsonl
        ├── MEMORY.md
        ├── attachments/
        └── scratch/
```

其中：

- `log.jsonl`：频道消息与机器人回复日志，也是上下文同步来源
- `MEMORY.md`：频道长期记忆
- `attachments/`：下载后的附件
- `scratch/`：该频道的临时工作目录
- `events/`：本地事件文件目录，可驱动即时、定时和周期任务

### mom 事件文件

除了实时飞书消息，mom 还支持通过 `.mom/events/` 下的 JSON 文件驱动任务。

支持三类事件：

- `immediate`：创建后尽快触发
- `one-shot`：在指定时间触发一次
- `periodic`：按固定秒数周期触发

示例：

```json
{
  "type": "immediate",
  "channelId": "oc_xxx",
  "text": "请总结今天频道里的待办项"
}
```

```json
{
  "type": "one-shot",
  "channelId": "oc_xxx",
  "text": "提醒大家提交日报",
  "at": "2026-04-08T10:00:00+08:00"
}
```

```json
{
  "type": "periodic",
  "channelId": "oc_xxx",
  "text": "检查频道里是否有未处理告警，如有则汇总",
  "interval_seconds": 3600
}
```

说明：

- `channelId` 对应聊天会话 ID。
- `text` 会作为一次 synthetic 聊天事件送进 Agent。
- `periodic` 事件会自动维护 `last_run`，用于控制下次触发时机。
- 如果周期事件不需要对外发言，可以让 Agent 返回 `[SILENT]`。

### mom 调试与展示策略

`mom` 默认面向群聊阅读体验，偏向“少噪音、只给结果”：

- 默认先发送占位文本，再在结束时替换为最终答复。
- 默认不展示流式 `delta`、内部 thinking、tool start/status/tool end 等中间过程。
- 打开 `MOM_SHOW_INTERMEDIATE_UPDATES=1` 后，可在流式模式下看到中间更新。
- 打开 `MOM_SHOW_TOOL_DETAILS=1` 后，会把工具调用摘要作为 detail 消息回发。
- 打开 `MOM_SHOW_THINKING=1` 后，会额外展示思考类事件。

如果需要更系统的模块说明，可继续阅读 [mom/mom模块.md](/Users/admin/PyCharmProject/LiuClaw/mom/mom模块.md)。

## 作为库使用

### 直接使用 `ai`

```python
import asyncio

from ai import Context, UserMessage, complete


async def main() -> None:
    message = await complete(
        model="openai:gpt-5",
        context=Context(
            systemPrompt="你是一个简洁的中文助手。",
            messages=[UserMessage(content="请一句话介绍 LiuClaw。")],
        ),
    )
    print(message.content)


asyncio.run(main())
```

### 使用 `agent_core`

```python
import asyncio

from ai import UserMessage
from agent_core import Agent, AgentLoopConfig


async def main() -> None:
    agent = Agent(
        AgentLoopConfig(
            model="openai:gpt-5",
            systemPrompt="你是一个代码助手。",
        )
    )
    await agent.send(UserMessage(content="请解释这个仓库的三层结构。"))

    async for event in await agent.run():
        if event.type == "message_update":
            print(event.messageDelta, end="")


asyncio.run(main())
```

更多示例见 [examples/openai_simple.py](/Users/admin/PyCharmProject/LiuClaw/examples/openai_simple.py) 和 [examples/anthropic_simple.py](/Users/admin/PyCharmProject/LiuClaw/examples/anthropic_simple.py)。

## 关键设计

- 非流式调用不是单独实现的另一套路径，`complete()` 本质上是对 `stream()` 的统一聚合。
- `agent_core` 不直接依赖具体厂商协议，而是通过 `ai` 的统一流式接口驱动 Agent 循环。
- `coding_agent` 不把逻辑塞进入口函数，而是把配置、资源、工具、会话和交互拆到独立组件中装配。
- `mom` 复用底层 Agent 会话能力，但额外补上频道级日志、记忆、事件调度和聊天平台回写，使 Agent 能稳定运行在群聊/私聊环境里。
- 会话摘要压缩与恢复是产品层能力，不污染 `ai` 与 `agent_core` 的纯运行时边界。
- 扩展机制已经预留工具、provider、监听器和系统提示扩展点，便于后续演进。

## 文档导航

- [ai/ai模块.md](/Users/admin/PyCharmProject/LiuClaw/ai/ai模块.md)
- [agent_core/agent-core模块.md](/Users/admin/PyCharmProject/LiuClaw/agent_core/agent-core模块.md)
- [coding_agent/coding-agent模块.md](/Users/admin/PyCharmProject/LiuClaw/coding_agent/coding-agent模块.md)
- [mom/mom模块.md](/Users/admin/PyCharmProject/LiuClaw/mom/mom模块.md)
- [tests/test_client.py](/Users/admin/PyCharmProject/LiuClaw/tests/test_client.py)
- [tests/test_agent_loop.py](/Users/admin/PyCharmProject/LiuClaw/tests/test_agent_loop.py)
- [tests/test_coding_agent.py](/Users/admin/PyCharmProject/LiuClaw/tests/test_coding_agent.py)
- [tests/test_mom.py](/Users/admin/PyCharmProject/LiuClaw/tests/test_mom.py)

## 适合从哪里读起

- 想看底层模型协议：先读 `ai`
- 想看 Agent 多轮循环：先读 `agent_core`
- 想看终端应用如何装配：先读 `coding_agent`
- 想看聊天机器人如何接入飞书并维持频道上下文：先读 `mom`
- 想看行为边界和当前契约：直接读 `tests/`
