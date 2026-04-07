from __future__ import annotations

from datetime import datetime
from platform import platform

from .types import SessionContext

BEHAVIOR_RULES = """行为准则：
- 你是终端中的编码助手，优先给出可执行的工程动作
- 调用工具前先想清楚最小必要范围
- 写文件前确保路径在工作区内
- 输出简洁、明确，并在需要时说明假设
"""


def _build_tools_markdown(tools_markdown: str) -> str:
    """把工具列表字符串包装成系统提示片段。"""

    return f"可用工具：\n{tools_markdown}" if tools_markdown else "可用工具：无"


def _build_skills_markdown(context: SessionContext) -> str:
    """把已加载技能压缩成适合放入系统提示的摘要。"""

    if not context.resources.skills:
        return "技能：无"
    lines = ["技能："]
    for skill in context.resources.skills:
        preview = skill.content.strip().splitlines()[0] if skill.content.strip() else ""
        lines.append(f"- {skill.name}: {preview}")
    return "\n".join(lines)


def build_system_prompt(context: SessionContext) -> str:
    """按固定顺序拼装最终发送给模型的系统提示。"""

    prompts = context.resources.prompts
    default_prompt = context.settings.system_prompt_override or prompts["SYSTEM"].content
    sections = [
        default_prompt.strip(),
        _build_tools_markdown(context.tools_markdown),
        BEHAVIOR_RULES.strip(),
    ]
    if context.resources.agents_context:
        sections.append(f"项目上下文（AGENTS.md）：\n{context.resources.agents_context.strip()}")
    sections.append(_build_skills_markdown(context))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sections.append(
        "\n".join(
            [
                "环境信息：",
                f"- 当前日期: {now}",
                f"- 当前目录: {context.cwd}",
                f"- 工作区根目录: {context.workspace_root}",
                f"- 模型: {context.model.id}",
                f"- 思考等级: {context.thinking or 'default'}",
                f"- 平台: {platform()}",
            ]
        )
    )
    return "\n\n".join(section for section in sections if section)
