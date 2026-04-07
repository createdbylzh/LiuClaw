# coding-agent 模块说明文档

## 1. 模块定位

`coding_agent` 是建立在 `ai` 模块与 `agent_core` 模块之上的产品化运行层。

它的职责不是重新实现一套大模型调用协议，也不是重新实现一套工具循环，而是把下面这些能力组装成一个可以直接运行的终端编码助手：

- 模型选择与切换
- 会话持久化与恢复
- 系统提示构建
- 内置文件/命令工具
- 上下文压缩
- 资源加载
- 终端交互模式

从职责分层上看：

- `ai`：统一 provider、模型、消息、流式事件
- `agent_core`：统一 agent loop、工具调用、steering、follow-up
- `coding_agent`：面向最终用户的产品运行平台

一句话总结：

`coding_agent` = 一个可扩展的终端编码助手运行平台。

---

## 2. 当前目录结构

当前模块目录如下：

```text
coding_agent/
├── __init__.py
├── __main__.py
├── main.py
├── coding-agent模块.md
├── cli/
│   ├── __init__.py
│   └── parser.py
├── config/
│   └── paths.py
├── core/
│   ├── __init__.py
│   ├── agent_session.py
│   ├── agents_context_loader.py
│   ├── model_registry.py
│   ├── prompts_loader.py
│   ├── resource_loader.py
│   ├── session_manager.py
│   ├── settings_manager.py
│   ├── skills_loader.py
│   ├── system_prompt.py
│   ├── themes_loader.py
│   ├── types.py
│   ├── compaction/
│   │   ├── __init__.py
│   │   ├── branch_summary.py
│   │   ├── compactor.py
│   │   └── triggers.py
│   └── tools/
│       ├── __init__.py
│       ├── bash.py
│       ├── common.py
│       ├── edit.py
│       ├── find.py
│       ├── grep.py
│       ├── ls.py
│       ├── read.py
│       └── write.py
└── modes/
    └── interactive/
        ├── __init__.py
        ├── app.py
        ├── controller.py
        ├── renderer.py
        └── state.py
```

---

## 3. 入口与启动流程

### 3.1 入口文件

- `coding_agent/__main__.py`
- `coding_agent/main.py`

因此模块支持以下启动方式：

```bash
python -m coding_agent
```

### 3.2 `main.py` 的启动流程

`coding_agent.main.main()` 的执行步骤如下：

1. 解析命令行参数
2. 解析当前工作目录 `cwd`
3. 初始化全局配置目录 `~/.LiuClaw/agent`
4. 读取全局设置与项目设置
5. 加载模型注册表
6. 根据 CLI 或默认设置选择模型
7. 初始化会话管理器
8. 初始化资源加载器
9. 创建 `AgentSession`
10. 按运行模式执行：
   - `--compact`：只压缩后退出
   - 传入 `prompt`：one-shot 模式执行一次
   - 默认：进入 interactive 模式

这说明 `main.py` 的角色是总装配入口，而真正的业务执行在 `AgentSession` 与 interactive 子系统中完成。

---

## 4. 配置体系

### 4.1 配置目录

全局配置目录由 `coding_agent/config/paths.py` 统一定义，根目录为：

```text
~/.LiuClaw/agent/
```

当前包含以下内容：

- `settings.json`：全局设置
- `models.json`：用户自定义模型
- `sessions/`：会话数据目录
- `skills/`：技能目录
- `prompts/`：提示模板目录
- `themes/`：主题目录
- `extensions/`：扩展目录

项目级配置文件路径为：

```text
.LiuClaw/settings.json
```

### 4.2 设置读取逻辑

`coding_agent/core/settings_manager.py` 负责读取设置。

设置合并顺序：

1. 全局设置 `~/.LiuClaw/agent/settings.json`
2. 项目设置 `.LiuClaw/settings.json`

项目设置覆盖全局设置。

### 4.3 当前支持的主要设置项

定义在 `coding_agent/core/types.py` 的 `CodingAgentSettings` 中：

- `default_model`
- `default_thinking`
- `auto_compact`
- `compact_threshold`
- `compact_keep_turns`
- `compact_model`
- `theme`
- `system_prompt_override`
- `tool_policy`

其中 `tool_policy` 进一步控制工具侧限制：

- `max_read_chars`
- `max_command_chars`
- `max_ls_entries`
- `max_find_entries`
- `allow_bash`

---

## 5. 模型体系

### 5.1 模型来源

`coding_agent/core/model_registry.py` 的 `ModelRegistry` 会把两部分模型合并：

1. `ai.models.list_models()` 返回的内置模型
2. `~/.LiuClaw/agent/models.json` 中定义的用户模型

因此 `coding_agent` 不直接耦合某个 provider，而是依赖 `ai` 层的统一模型目录。

### 5.2 对上层的意义

只要某个 provider 已在 `ai` 模块中接入，并且对应模型进入了 `ai.models`，理论上 `coding_agent` 就可以直接使用该模型。

这也是为什么新增 provider 后，`coding_agent` 不需要重写一层 provider 逻辑。

---

## 6. 资源加载体系

### 6.1 总入口

`coding_agent/core/resource_loader.py` 的 `ResourceLoader` 是统一资源加载入口。

它会加载以下资源：

- skills
- prompts
- themes
- AGENTS.md
- extensions

最终返回一个 `ResourceBundle`。

### 6.2 Skills

`coding_agent/core/skills_loader.py`

扫描规则：

- 递归扫描 `skills/` 下的 `SKILL.md`
- 支持 `skills/<name>/SKILL.md` 结构

加载后形成 `SkillResource`：

- `name`
- `path`
- `content`

### 6.3 Prompts

`coding_agent/core/prompts_loader.py`

行为：

- 加载 `prompts/*.md`
- 若不存在 `SYSTEM.md`，则自动使用内置默认系统提示

### 6.4 Themes

`coding_agent/core/themes_loader.py`

行为：

- 加载 `themes/*.json`
- 若不存在 `default` 主题，则自动构造一个默认主题

### 6.5 AGENTS.md

`coding_agent/core/agents_context_loader.py`

行为：

- 从当前工作区向上查找最近的 `AGENTS.md`
- 找到后直接读取全文

### 6.6 Extensions

当前 `extensions` 仍然是占位设计。

`ResourceLoader._scan_extensions()` 的行为是：

- 扫描扩展目录
- 读取扩展路径或 `extension.json`
- 生成 `ExtensionResource`

当前不会执行扩展代码。

### 6.7 冲突检测

资源加载完成后会做跨类型重名检测。

冲突类型包括：

- skill
- prompt
- theme
- extension

如果同名，会抛出 `ValueError`。

---

## 7. 系统提示构建

### 7.1 核心文件

`coding_agent/core/system_prompt.py`

### 7.2 组装顺序

当前系统提示按以下顺序构建：

1. 用户覆盖的 `system_prompt_override` 或 `SYSTEM` prompt
2. 工具说明
3. 行为准则
4. 项目上下文 `AGENTS.md`
5. skills 摘要
6. 当前日期、工作目录、工作区、模型、thinking、平台信息

### 7.3 行为准则

当前内置行为准则强调：

- 是终端编码助手
- 优先给出可执行工程动作
- 工具调用要控制范围
- 写文件前要保证路径在工作区内
- 输出简洁明确

---

## 8. 会话核心：`AgentSession`

### 8.1 模块定位

`coding_agent/core/agent_session.py`

这是整个 `coding_agent` 的核心对象。

它的职责是把以下子系统组织到一起：

- 模型
- 设置
- 工具
- 资源
- 系统提示
- `agent_core.Agent`
- 会话存储
- 自动压缩
- steering / follow-up
- interactive 事件映射

### 8.2 内部持有的关键对象

`AgentSession` 主要保存：

- `workspace_root`
- `cwd`
- `model`
- `thinking`
- `settings`
- `session_manager`
- `resource_loader`
- `resources`
- `tools`
- `session_id`
- `branch_id`
- `compactor`
- `_agent`

其中 `_agent` 是来自 `agent_core` 的高层 `Agent`。

### 8.3 初始化流程

初始化时会做这些事：

1. 加载资源
2. 构造默认工具列表
3. 构造 `SessionCompactor`
4. 基于 `AgentLoopConfig` 创建底层 `agent_core.Agent`
5. 把以下 hooks 接到底层 loop：
   - `steer=self._steer`
   - `followUp=self._follow_up`
   - `beforeToolCall=self._before_tool_call`
   - `afterToolCall=self._after_tool_call`
6. 若没有显式传 `session_id`，则自动创建新会话

### 8.4 关键公开方法

#### `send_user_message(content)`

作用：

- 把用户消息写入会话存储
- 更新 `last_node_id`
- 把消息送入底层 agent 待处理队列

#### `resume_session()`

作用：

- 从持久化存储恢复会话消息
- 重建系统提示
- 把历史、模型、thinking、工具同步到底层 `Agent`

#### `switch_model(model)`

作用：

- 切换当前模型
- 更新底层 `Agent`
- 重建系统提示
- 更新会话元信息中的 `model_id`

#### `set_thinking(thinking)`

作用：

- 调整思考等级
- 更新底层 `Agent`
- 重建系统提示

#### `compact()`

作用：

- 手动压缩当前分支上下文

#### `cancel()`

作用：

- 取消当前运行中的 agent loop

#### `list_recent_sessions()`

作用：

- 获取当前工作区最近会话，用于 interactive 层展示

#### `get_last_user_message()`

作用：

- 获取最近一条真实用户输入
- 会过滤 steering / follow-up 控制消息

#### `run_turn()`

这是最关键的方法。

职责：

- 重置本轮 steering/follow-up 状态
- 根据当前上下文决定继续对话还是新起一轮
- 必要时自动压缩
- 驱动底层 `Agent.run()` 或 `continueConversation()`
- 把 `agent_core` 事件转换为 `SessionEvent`
- 在事件流过程中把 assistant / tool / 控制消息持久化

---

## 9. SessionEvent 事件模型

### 9.1 定义位置

`coding_agent/core/types.py`

### 9.2 当前事件类型

当前 `SessionEventType` 包括：

- `status`
- `thinking`
- `message_start`
- `message_delta`
- `message_end`
- `tool_start`
- `tool_update`
- `tool_end`
- `error`

### 9.3 当前事件字段

`SessionEvent` 当前包含：

- `type`
- `message`
- `delta`
- `tool_name`
- `error`
- `panel`
- `status_level`
- `is_transient`
- `tool_arguments`
- `tool_output_preview`
- `message_id`
- `payload`

这说明 `SessionEvent` 已经不只是简单字符串，而是为上层 UI 准备的结构化事件。

### 9.4 事件映射规则

`AgentSession._map_event()` 负责把 `agent_core.AgentEvent` 映射成 `SessionEvent`。

主要规则如下：

- assistant 开始输出时发 `message_start`
- 流式文本增量发 `message_delta`
- 最终 assistant 文本发 `message_end`
- assistant thinking 会额外发 `thinking`
- steering/follow-up 控制消息转为 `status`
- 工具开始、更新、结束分别转为 `tool_start/tool_update/tool_end`
- agent 报错时转为 `error`

---

## 10. steering 与 follow-up

### 10.1 作用

`coding_agent` 不是只展示工具事件，而是把 `agent_core` 的 steering/follow-up 真实接到了会话编排里。

### 10.2 当前实现方式

#### `beforeToolCall -> _before_tool_call`

在工具执行前：

- 设置本轮发生过工具活动
- 往 `_pending_steering_messages` 中压入一条控制消息

#### `afterToolCall -> _after_tool_call`

在工具执行后：

- 再压入一条 steering 控制消息
- 告诉模型工具已经执行完成，可以继续工作

#### `_steer()`

作用：

- 把待发送 steering 消息交给底层 loop
- 一旦取出就清空待发送队列

#### `_follow_up()`

作用：

- 当工具已执行且还没有 follow-up 时
- 自动插入一条“请基于工具结果继续整理最终答复”的控制消息

### 10.3 当前效果

这样一来：

- 模型会在工具执行前后收到控制性插话
- 工具完成后会自动触发最后一轮总结
- interactive 层会把这些内部控制消息以状态提示展示，而不是当成普通用户消息

---

## 11. 会话持久化体系

### 11.1 核心文件

`coding_agent/core/session_manager.py`

### 11.2 存储结构

每个会话位于：

```text
~/.LiuClaw/agent/sessions/<session_id>/
```

当前包含两个核心文件：

- `meta.json`
- `events.jsonl`

### 11.3 `meta.json`

当前元信息大致包含：

- `session_id`
- `title`
- `current_branch`
- `cwd`
- `model_id`
- `created_at`
- `updated_at`

### 11.4 `events.jsonl`

这是事件源文件，按 JSONL 逐条追加。

当前支持的事件类型包括：

- `message`
- `summary`
- `branch_switch`

### 11.5 会话消息节点

消息持久化后会变成 `PersistedMessageNode`，包含：

- `id`
- `role`
- `content`
- `parent_id`
- `branch_id`
- `thinking`
- `tool_calls`
- `tool_name`
- `tool_call_id`
- `metadata`

### 11.6 恢复逻辑

`load_session(session_id)` 会：

1. 读取 `meta.json`
2. 回放 `events.jsonl`
3. 重建：
   - 当前分支
   - 消息节点
   - 摘要列表

### 11.7 构建模型上下文

`build_context_messages()` 的行为：

1. 找到当前分支
2. 查找该分支最近摘要
3. 把摘要插入上下文最前部
4. 对已经被摘要覆盖的节点不再重复注入
5. 返回统一消息列表

### 11.8 recent sessions

`list_recent_sessions()` 用于 interactive 层恢复会话：

- 按 `updated_at` 倒序排序
- 支持按 `cwd` 过滤

---

## 12. 压缩体系

### 12.1 核心文件

位于 `coding_agent/core/compaction/`

- `compactor.py`
- `triggers.py`
- `branch_summary.py`

### 12.2 当前压缩策略

`SessionCompactor.compact_session()` 的当前策略很直接：

1. 读取当前分支全部节点
2. 保留最近 `keep_turns * 2` 条消息
3. 其余旧消息作为压缩候选
4. 通过 `_summarize_nodes()` 生成纯文本摘要
5. 把摘要事件写回 `events.jsonl`

### 12.3 当前摘要生成方式

当前不是调用模型生成摘要，而是本地规则摘要：

- 用户/助手/工具消息逐条整理
- 内容截断到 120 字

### 12.4 触发器

`triggers.py` 中 `should_compact()` 会根据：

- `auto_compact`
- `compact_threshold`
- 上下文 token 比例
- 是否超出模型窗口

来决定是否自动压缩。

### 12.5 当前局限

当前压缩是可用的，但仍然是基础版：

- 摘要不是模型生成，而是本地拼接
- 分支摘要只提供简单入口
- 没有更复杂的摘要分层或记忆提取

---

## 13. 工具体系

### 13.1 总入口

`coding_agent/core/tools/__init__.py`

`build_default_tools()` 当前会构造 7 个内置工具：

- `read`
- `write`
- `edit`
- `bash`
- `grep`
- `find`
- `ls`

### 13.2 共同能力

`coding_agent/core/tools/common.py` 提供了三类公共能力：

- `ensure_within_workspace()`：禁止越出工作区
- `truncate_text()`：限制输出体积
- `run_shell()`：统一执行 shell 命令

### 13.3 各工具说明

#### `read`

- 读取 UTF-8 文本文件
- 受 `max_read_chars` 限制

#### `write`

- 写入 UTF-8 文本文件
- 自动创建父目录

#### `edit`

支持两种编辑方式：

- `old/new` 的单次精确替换
- `start_line/end_line/replacement` 的行范围替换

#### `bash`

- 执行非交互 shell 命令
- 返回退出码、stdout、stderr
- 受 `allow_bash` 控制
- 输出长度受 `max_command_chars` 限制

#### `grep`

- 基于 `rg` 搜索文本
- 支持指定路径

#### `find`

- 在工作区内递归查找文件名片段
- 受 `max_find_entries` 限制

#### `ls`

- 列出目录下的直接子项
- 受 `max_ls_entries` 限制

### 13.4 工具安全边界

当前工具的核心安全原则：

- 写操作必须位于工作区内
- 读操作也要求位于工作区内
- shell 命令工作目录固定为工作区根目录
- 长输出统一截断，避免把过量内容灌回模型

---

## 14. interactive 模式

### 14.1 子系统结构

位于 `coding_agent/modes/interactive/`

当前分为四部分：

- `app.py`
- `state.py`
- `renderer.py`
- `controller.py`

这代表 interactive 已经不是“单类 + print”的结构，而是一个有状态的终端应用。

### 14.2 `InteractiveApp`

作用：

- 负责组装 interactive 子系统
- 创建 `InteractiveState`
- 创建 `InteractiveRenderer`
- 创建 `InteractiveController`
- 启动 `prompt_toolkit.Application`

如果当前环境没有 `prompt_toolkit`，会降级到 `_fallback_loop()`。

### 14.3 `InteractiveState`

作用：

- 保存当前 UI 可见状态

当前主要字段包括：

- `session_id`
- `model_id`
- `thinking`
- `cwd`
- `theme`
- `submit_on_enter`
- `is_running`
- `last_error`
- `status_message`
- `current_tool`
- `output_cards`
- `thinking_cards`
- `tool_cards`
- `status_timeline`
- `recent_sessions`

它还负责把 `SessionEvent` 应用为 UI 状态变更。

### 14.4 `InteractiveRenderer`

作用：

- 使用 `prompt_toolkit` 把状态渲染成终端界面

当前布局包括：

1. 主输出区
2. 侧边状态区
3. 输入提示区
4. 输入区
5. 底部状态栏

### 14.5 当前快捷键

目前渲染器中已绑定：

- `Enter`：提交
- `Esc + Enter`：换行
- `Ctrl-C`：取消运行
- `Ctrl-L`：清空输出
- `Tab`：命令补全
- `Ctrl-R`：显示历史提示
- `PageUp/PageDown`：按页滚动主输出区
- `Esc + Up/Down`：按行滚动主输出区
- `F6`：在输入区和主输出区之间切换焦点

### 14.6 `InteractiveController`

作用：

- 处理输入内容
- 调度命令
- 触发 `AgentSession`
- 推动 UI 刷新

它是 interactive 的控制中枢。

### 14.7 当前斜杠命令

当前已实现：

- `/new`
- `/resume [session_id]`
- `/model <model_id>`
- `/thinking <low|medium|high>`
- `/compact`
- `/theme <theme_name>`
- `/pwd`
- `/sessions`
- `/help`
- `/clear`
- `/retry`
- `/exit`

### 14.8 命令补全

`CommandCompleter` 当前支持：

- 命令名补全
- `/model` 的模型补全
- `/resume` 的 session id 补全
- `/theme` 的主题补全
- `/thinking` 的级别补全

### 14.9 当前滚动能力

主输出区目前支持：

- 历史内容保留
- 按页滚动
- 按行滚动

不过侧边栏仍然没有独立滚动能力。

---

## 15. one-shot 与 interactive 的差异

### 15.1 one-shot

当 CLI 传入 `prompt` 时，`main.py` 走 one-shot 路径：

- 创建 `AgentSession`
- 发送一条用户消息
- 直接用 `InteractiveApp._render_event()` 做简单输出
- 不启动完整 TUI

### 15.2 interactive

默认路径会进入 `InteractiveApp.run()`：

- 启动 `prompt_toolkit` 全屏终端界面
- 接收持续输入
- 展示会话状态、工具状态、recent sessions 等

---

## 16. 数据流总览

下面是一次用户提问的完整数据流：

1. 用户在 CLI 或 TUI 输入问题
2. `InteractiveController` 调用 `AgentSession.send_user_message()`
3. 用户消息写入 `SessionManager`
4. `AgentSession.run_turn()` 开始执行
5. `AgentSession` 重建系统提示、上下文、工具
6. `AgentSession` 驱动 `agent_core.Agent`
7. `agent_core` 调用 `ai.streamSimple()`
8. `ai` 根据模型选择 provider
9. provider 返回统一流式事件
10. `agent_core` 执行工具、注入 steering/follow-up
11. `AgentSession` 把底层事件映射为 `SessionEvent`
12. interactive 状态层更新消息卡片、工具卡片、状态时间线
13. renderer 刷新终端界面
14. assistant / tool / control message 继续写入 `SessionManager`
15. 如有需要，压缩器写入摘要事件

---

## 17. 当前设计优点

### 17.1 分层清晰

`coding_agent` 没有直接耦合 provider 实现，而是站在 `ai` 与 `agent_core` 的统一接口之上。

### 17.2 扩展成本低

新增 provider、模型、工具或主题时，上层改动较小。

### 17.3 会话可恢复

采用 `events.jsonl` 事件源方式，便于后续扩展更多事件类型。

### 17.4 interactive 已具备产品雏形

现在已经不是简单 REPL，而是有状态的终端工作台。

---

## 18. 当前已知问题与限制

虽然模块已经可以运行，但当前实现仍有一些明显限制：

### 18.1 压缩仍偏基础

- 当前摘要是本地拼接，不是调用模型生成
- 压缩质量有限

### 18.2 扩展系统还未落地

- 只做扫描与冲突检测
- 不执行扩展逻辑

### 18.3 interactive 还不算完整 IDE

- 侧边栏不支持独立滚动
- thinking 还没有折叠/展开交互
- 工具输出没有更细粒度展开视图
- 输入模式切换还比较基础

### 18.4 会话分支能力未完全产品化

- 底层有 branch_id 与摘要能力
- 但 UI 暂未提供完整分支切换体验

### 18.5 部分内部接口仍有改进空间

例如：

- `AgentSession.switch_model()` 当前直接调用了 `SessionManager` 的私有方法 `_read_meta/_write_meta`
- 说明后续可以考虑给 `SessionManager` 补正式公开接口

---

## 19. 当前测试覆盖情况

从现有测试来看，模块已经覆盖了这些方向：

- 配置与设置合并
- 资源加载与冲突检测
- 会话管理与压缩
- 工具链基本行为
- `AgentSession` 基本流转
- steering / follow-up 的使用
- recent sessions
- interactive controller 命令
- renderer 历史内容保留与滚动接口
- 主入口与 CLI

这说明该模块已经具备较好的基础回归保障。

---

## 20. 建议的后续演进方向

如果继续完善 `coding_agent`，建议优先级如下：

### 第一优先级

- 让压缩改为真正的模型摘要
- 为 provider 错误、429、超时增加重试与更友好的 UI 提示
- 让 interactive 侧边栏支持独立滚动
- 完善 `/resume` 的可选列表与选择体验

### 第二优先级

- 做真正可执行的 extensions 系统
- 提供会话分支浏览与切换
- 为 thinking / tool output 加可折叠展示

### 第三优先级

- 增加更丰富的主题系统
- 增加文件树、diff 视图、结构化选择器
- 把 interactive 进一步提升为更完整的终端 IDE 工作台

---

## 21. 结论

当前 `coding_agent` 模块已经完成了从“运行时骨架”到“基础产品层”的第一轮建设。

它已经具备以下关键能力：

- 可以启动
- 可以选择模型
- 可以加载资源
- 可以调用工具
- 可以持久化会话
- 可以恢复历史
- 可以自动压缩上下文
- 可以在终端中交互运行

从工程角度看，它现在已经是一个真实可运行的模块，而不是一个纯概念目录。

如果后续继续演进，它最值得投入的方向会是：

- 提升摘要与错误恢复质量
- 增强 interactive 产品体验
- 落实真正的扩展系统
- 打磨会话分支与长期记忆能力

