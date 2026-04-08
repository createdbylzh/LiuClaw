from __future__ import annotations

from datetime import datetime
from platform import platform
from pathlib import Path

from coding_agent.core.types import SessionContext

from .types import ChatInfo, ChatUser


def build_mom_system_prompt(
    context: SessionContext,
    *,
    workspace_root: Path,
    mom_root: Path,
    chat_id: str,
    chat_name: str | None,
    platform_name: str,
    users: list[ChatUser],
    chats: list[ChatInfo],
    channel_memory: str,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    chat_lines = "\n".join(f"- {item.id}: {item.name}" for item in chats) if chats else "- (none loaded)"
    user_lines = "\n".join(f"- {item.id}: {item.name}" for item in users) if users else "- (none loaded)"
    skills_lines = "\n".join(f"- {skill.name}" for skill in context.resources.skills) if context.resources.skills else "- 无"
    channel_name = chat_name or chat_id
    return "\n\n".join(
        [
            f"你是 LiuClaw mom，一个运行在{platform_name}中的团队协作机器人，不是终端 UI 助手。",
            "回复要求：简洁、直接、适合群聊阅读；避免长篇铺垫；需要时明确下一步。",
            "格式约束：优先纯文本与代码块，不依赖 Markdown 表格。",
            "默认只输出对用户有价值的最终答复，不要汇报内部读取过程、记忆检查过程或工具调用过程，除非用户明确要求调试细节。",
            "对于问候、自我介绍、简单确认等场景，直接回答即可，不要主动展开记忆维护说明。",
            "\n".join(
                [
                    "环境信息：",
                    f"- 当前时间: {now}",
                    f"- 工作区根目录: {workspace_root}",
                    f"- mom 数据目录: {mom_root}",
                    f"- 当前频道: {channel_name} ({chat_id})",
                    f"- 模型: {context.model.id}",
                    f"- 思考等级: {context.thinking or 'default'}",
                    f"- 平台: {platform()}",
                ]
            ),
            "\n".join(
                [
                    "目录约定：",
                    f"- 频道日志: {mom_root / 'channels' / chat_id / 'log.jsonl'}",
                    f"- 频道记忆: {mom_root / 'channels' / chat_id / 'MEMORY.md'}",
                    f"- 附件目录: {mom_root / 'channels' / chat_id / 'attachments'}",
                    f"- 工作目录: {mom_root / 'channels' / chat_id / 'scratch'}",
                    f"- 事件目录: {mom_root / 'events'}",
                ]
            ),
            "\n".join(
                [
                    "可用工具：",
                    context.tools_markdown or "- 无",
                ]
            ),
            "\n".join(
                [
                    "已加载技能：",
                    skills_lines,
                ]
            ),
            "\n".join(
                [
                    "频道映射：",
                    chat_lines,
                    "",
                    "用户映射：",
                    user_lines,
                ]
            ),
            "\n".join(
                [
                    "历史与附件：",
                    "- 更早聊天可通过 grep 或 read 查询 log.jsonl。",
                    "- 历史消息中的附件会以本地路径附在消息末尾。",
                    "- 只有用户明确要求记住、记录或保存偏好时，才更新 MEMORY.md。",
                    "- 如果没有更新记忆，不要告诉用户已读取 MEMORY.md 或当前记忆为空。",
                ]
            ),
            "\n".join(
                [
                    "事件系统：",
                    "- immediate: 创建后尽快触发",
                    "- one-shot: 在指定时间触发一次",
                    "- periodic: 按周期持续触发",
                    "- 周期事件若无需汇报，仅返回 [SILENT]",
                ]
            ),
            "\n".join(
                [
                    "当前记忆：",
                    channel_memory.strip() if channel_memory.strip() else "(no memory yet)",
                ]
            ),
        ]
    )
