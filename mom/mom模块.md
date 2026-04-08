# mom 模块总结

## 1. 模块定位

`mom` 模块是 LiuClaw 在聊天平台场景下的一层适配与运行编排模块。它把“飞书消息事件”转换成内部统一事件，再把这些事件交给底层 Agent 会话执行，最后把执行结果重新发送回聊天会话。

从职责上看，这个模块不是通用 UI，也不是底层模型调用层，而是一个“群聊/私聊机器人运行壳”：

- 对外负责接入飞书事件、发送文本与文件、维护频道消息上下文。
- 对内负责把聊天记录同步到 Agent 会话、生成系统提示词、驱动一次完整的 Agent turn。
- 对持久化负责保存频道日志、记忆文件、附件、事件文件和会话引用关系。

## 2. 模块目录与文件职责

### `mom/main.py`

应用主入口。

- `MomConfig`：从环境变量读取启动配置。
- `MomApp`：应用编排中心，负责装配 `store`、`transport`、`events watcher`、`runner` 和模型。
- `handle_chat_event()`：处理每条聊天事件，包括去重、stop 指令、并发控制和排队。
- `_run_event()`：真正执行一次任务，并在结束后继续处理队列里的下一条事件。

### `mom/feishu.py`

飞书接入层。

- `FeishuConfig`：飞书连接参数。
- `FeishuBotTransport`：封装飞书 API 调用、长连接/webhook 接入、事件解析、消息发送、消息更新、附件下载。
- `parse_event()`：把飞书原始事件转成内部统一的 `ChatEvent`。
- `create_context()`：把平台能力包装成 `ChatContext`，交给 runner 使用。

### `mom/runner.py`

执行层，是 mom 的核心运行逻辑。

- `MomAgentSession`：基于 `AgentSession` 的场景化扩展，负责生成 mom 的系统提示词。
- `MomRunner`：执行一次会话请求，包含历史同步、调用 Agent、消费流式事件、向飞书回写结果。
- `get_or_create_runner()`：按 `chat_id` 复用 runner，保证频道级串行和会话连续性。

### `mom/context_sync.py`

上下文同步层。

- 从频道 `log.jsonl` 中提取历史用户消息。
- 把还未同步过的消息追加到 Agent session tree。
- 通过 `synced_message_ids` 防止重复注入同一条聊天记录。

它的作用是保证 Agent 不是只看到“当前这条消息”，而是能继承频道已有对话上下文。

### `mom/prompt.py`

系统提示词拼装层。

它会把以下内容整合到系统 prompt 中：

- 当前时间、平台、工作区、mom 目录
- 当前频道和已知用户/频道映射
- 工具列表、技能列表
- 频道日志、记忆、附件和事件目录约定
- 对机器人回复风格和记忆更新时机的约束

这个文件决定了 mom 在聊天环境中的行为边界和表达方式。

### `mom/store.py`

本地持久化层。

核心职责：

- 统一构造 `.mom` 目录结构
- 管理频道目录、附件目录、scratch 目录
- 读写 `settings.json`、`channel_index.json`
- 记录聊天日志 `log.jsonl`
- 保存频道与 Agent session 的关联关系

这是 mom 的数据基础设施层，几乎所有其他模块都会依赖它。

### `mom/events.py`

本地事件文件轮询器。

支持三种事件类型：

- `immediate`：创建后立即触发
- `one-shot`：到指定时间触发一次
- `periodic`：按间隔循环触发

它的价值在于：除了实时聊天消息，mom 也能通过事件文件驱动定时任务或系统消息任务。

### `mom/types.py`

统一类型定义层。

这个文件定义了 mom 内部的主要数据模型，包括：

- `ChatEvent`
- `ChatAttachment`
- `ChatContext`
- `RunResult`
- `SessionRef`
- `ChannelState`
- `LoggedChatMessage`
- `MomPaths`

它让各模块之间的数据边界清晰、稳定，也降低了耦合。

## 3. 核心执行链路

mom 模块的完整处理流程可以概括为下面这条链：

1. 飞书收到一条消息。
2. `FeishuBotTransport.parse_event()` 把原始事件解析成 `ChatEvent`。
3. `MomStore.log_event()` 把用户消息写入频道日志。
4. `MomApp.handle_chat_event()` 决定是否触发执行。
5. `MomApp._run_event()` 取到该频道对应的 `runner` 和 `session_ref`。
6. `sync_channel_log_to_session()` 把历史日志中的用户消息同步进 Agent 会话。
7. `MomAgentSession._build_system_prompt()` 结合当前频道上下文生成系统提示词。
8. `MomRunner.run()` 把当前消息送入 Agent，并消费 `SessionEvent` 流。
9. `_handle_event()` 根据渲染配置决定是否显示中间过程、工具信息、思考内容。
10. 最终回复通过 `ChatContext.respond()` 或 `replace_message()` 回写到飞书，并记录到日志。

这条链说明：mom 的设计重点不是“单次调用模型”，而是“长期维持一个频道级连续会话”。

## 4. 关键数据结构与状态

### 4.1 `ChatEvent`

这是所有输入的统一抽象，既可以来自飞书实时消息，也可以来自 `events` 目录中的系统事件。

关键字段：

- `chat_id`：频道或私聊会话 ID
- `message_id`：消息唯一标识
- `sender_id` / `sender_name`：发送者信息
- `text`：规范化后的正文
- `attachments`：附件列表
- `is_direct`：是否为私聊
- `is_trigger`：是否应该触发机器人执行
- `metadata`：原始事件或附加标记，例如 `synthetic`

### 4.2 `ChannelState`

这是 `MomApp` 维护的频道运行态，主要解决并发问题。

关键字段：

- `running`：当前频道是否正在处理任务
- `runner`：当前频道复用的 runner
- `stop_requested`：是否收到停止请求
- `queued_events`：忙碌期间排队的事件
- `recent_incoming_message_ids`：最近处理过的消息 ID，用于去重

### 4.3 `SessionRef`

它连接“聊天频道”和“Agent 会话”：

- `session_id`：底层会话 ID
- `branch_id`：当前分支
- `synced_message_ids`：已经同步进会话的聊天消息 ID

这让 mom 可以跨多轮对话复用同一条 Agent 会话，而不是每次都新开一轮。

## 5. 持久化设计

mom 会在工作区下维护 `.mom` 目录。典型结构如下：

```text
.mom/
  settings.json
  channel_index.json
  events/
  sessions/
  channels/
    <chat_id>/
      log.jsonl
      MEMORY.md
      attachments/
      scratch/
```

### `log.jsonl`

保存频道级消息历史，包括：

- 用户消息
- 机器人主回复
- 调试明细消息

这个文件既是审计记录，也是后续会话同步的来源。

### `MEMORY.md`

保存该频道的长期记忆。系统 prompt 中已经明确约束：只有在用户明确要求“记住、记录、保存偏好”时才应该更新这里。

### `channel_index.json`

保存 `chat_id -> session_ref` 的映射。它是频道连续会话能力的关键。

## 6. 并发与串行策略

mom 明确采用“频道内串行、频道间可并行”的思路。

### 频道内串行

`MomApp.handle_chat_event()` 中有一套简单但有效的控制逻辑：

- 如果该频道已有任务运行中，普通新消息不会直接并发执行。
- 用户会收到“正在处理当前频道任务，可发送 stop 中断”提示。
- 如果事件是系统合成事件（`synthetic=True`），会被加入 `queued_events` 队列。
- 当前任务结束后，队列中的下一条事件会继续执行。

这样可以避免多条消息并发写同一个会话，造成上下文错乱。

### 停止机制

当用户发送 `stop` 时：

- `state.stop_requested = True`
- `runner.abort()` 调用底层 session cancel
- 如果运行确实因为取消而结束，就回复“已停止。”

这说明 mom 对“可中断执行”有明确支持。

## 7. 输出渲染策略

`MomRenderConfig` 控制聊天侧看见多少执行细节。

主要开关：

- `render_mode`
- `placeholder_text`
- `show_intermediate_updates`
- `show_tool_details`
- `show_thinking`

默认设计是“尽量只给用户最终答案”：

- `message_delta` 默认不实时刷屏，只累计文本。
- `thinking` 默认不展示。
- `tool_start/tool_end/status` 默认不展示。
- `message_end` 时再统一替换成最终答复。

这个策略非常适合群聊机器人，因为能减少噪音和调试信息泄漏。

## 8. 飞书适配层的设计要点

### 8.1 文本规范化

`_normalize_text_message()` 会：

- 去掉非法控制字符
- 统一换行
- 限制飞书消息长度
- 空文本时给出占位内容

这是典型的平台输出保护逻辑。

### 8.2 @ 提及清洗

`_strip_mentions()` 会从正文中剔除 `@mom` 等 mention 文本，只保留用户真正的指令内容。

例如：

```text
@mom 请帮我分析一下
```

会被转成：

```text
请帮我分析一下
```

### 8.3 触发规则

在飞书事件解析后：

- 私聊消息天然触发：`is_direct=True -> is_trigger=True`
- 群聊只有被 @ 时才触发：`bool(mentions) -> is_trigger=True`

这个规则能降低机器人在群里被动刷屏的概率。

## 9. 事件系统的作用

`events.py` 让 mom 除了响应“人发来的消息”，还可以响应“系统定义的定时/计划事件”。

三类事件含义如下：

- `immediate`：适合立刻执行的一次性任务
- `one-shot`：适合某个具体时间点触发
- `periodic`：适合固定周期任务

其中 `periodic` 事件会在触发后回写 `last_run`，从而控制下次执行时间。

这套机制说明 mom 已经具备一定“自动任务机器人”的基础能力，而不仅仅是被动问答机器人。

## 10. 设计上的优点

### 优点 1：职责分层比较清晰

可以明显看到：

- 平台接入在 `feishu.py`
- 运行编排在 `main.py`
- 执行逻辑在 `runner.py`
- 存储在 `store.py`
- 类型定义在 `types.py`
- 历史同步在 `context_sync.py`

这是比较稳健的模块拆分方式。

### 优点 2：会话连续性做得比较完整

通过 `log.jsonl + SessionRef + sync_channel_log_to_session()` 这套设计，mom 可以在多轮聊天中保持连续上下文，而不是每次只处理单条消息。

### 优点 3：对聊天场景做了专门优化

例如：

- 默认只展示最终答复
- 支持 stop 中断
- 群聊只在被 @ 时触发
- 频道内串行执行

这些都非常贴近真实聊天机器人需求。

### 优点 4：支持系统事件扩展

本地事件目录让后续接入自动提醒、定时巡检、日报触发这类能力变得很自然。

## 11. 当前实现中的几个关键注意点

### 注意点 1：runner 是按 `chat_id` 全局缓存的

`get_or_create_runner()` 使用 `_RUNNERS` 做全局复用。好处是频道上下文稳定、避免重复创建；但也意味着：

- 生命周期较长
- 如果未来配置、模型、目录发生变化，需要额外考虑刷新策略

### 注意点 2：日志同步只同步非 bot 消息

`sync_channel_log_to_session()` 会跳过 `is_bot=True` 的记录，这表示 Agent 的历史上下文主要来自用户输入和附件，不会把自己之前的输出再次写回用户消息树中。

这是合理的，但要意识到：底层 session 本身仍然保存了模型历史，所以“机器人自己的历史”主要由 session tree 承担，而不是靠日志回灌。

### 注意点 3：去重依赖 message_id

无论是 `MomApp` 的最近消息缓存，还是 `SessionRef.synced_message_ids`，都高度依赖 `message_id` 稳定且唯一。如果外部平台在某些情况下重复投递、补发或生成新 ID，需要进一步评估去重策略。

### 注意点 4：webhook 与长连接都支持，但默认偏长连接

`serve()` 默认走 long connection。部署时需要确保：

- 飞书 SDK 已安装
- 应用凭证配置正确
- 对应模式的网络环境可用

## 12. 一句话总结

`mom` 模块本质上是一个“面向飞书聊天场景的 Agent 运行框架适配层”。它把消息平台、持久化存储、系统提示词、历史上下文同步、Agent 执行流和结果回写整合在一起，目标是让 LiuClaw 能以一个稳定、可连续对话、可被中断、可扩展为定时任务机器人的形态运行起来。
