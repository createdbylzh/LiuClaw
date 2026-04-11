from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai import Context, Model, ProviderRegistry, UserMessage, completeSimple

from ..session_manager import SessionManager
from ..types import CompactResult, CodingAgentSettings

SUMMARY_SYSTEM_PROMPT = """你是一个会话压缩器，负责把较早的 Agent 历史整理成后续继续工作的摘要。

请严格遵守以下要求：
1. 只输出下面 5 个一级标题，顺序不可改变：
任务目标
关键上下文
已完成事项
未完成事项
风险与注意点
2. 每个标题下使用简洁短句或短列表，不要写寒暄、解释或额外标题。
3. 保留后续继续任务真正需要的信息，避免复述无关细节。
4. 如果信息不足，也要保留标题，并写“暂无”。
5. 若涉及工具调用，优先总结工具名、用途、关键结果和失败信息。
6. 不要输出 Markdown 代码块。
"""


@dataclass(slots=True)
class CompactionRuntime:
    """描述压缩摘要生成时所需的运行时依赖。"""

    model: Model
    thinking: str | None
    settings: CodingAgentSettings
    registry: ProviderRegistry | None = None
    model_resolver: Any | None = None


class SessionCompactor:
    """负责选择旧消息并生成会话摘要。"""

    def __init__(
        self,
        session_manager: SessionManager,
        runtime: CompactionRuntime,
        keep_turns: int = 4,
    ) -> None:
        """初始化压缩器并配置保留的最近对话轮数。"""

        self.session_manager = session_manager  # 会话管理器。
        self.runtime = runtime  # 摘要生成所需运行时。
        self.keep_turns = keep_turns  # 压缩时保留的最近 turn 数。

    async def compact_session(self, session_id: str, branch_id: str | None = None) -> CompactResult:
        """压缩指定会话分支的旧消息并写入摘要事件。"""

        snapshot = self.session_manager.load_session(session_id)
        active_branch = branch_id or snapshot.branch_id
        nodes = [node for node in snapshot.nodes if node.branch_id == active_branch]
        keep_count = self.keep_turns * 2
        compacted = nodes[:-keep_count] if len(nodes) > keep_count else []
        if not compacted:
            return CompactResult(summary="", compacted_count=0, branch_id=active_branch, node_ids=[])
        summary = await self._summarize_nodes(compacted)
        if not summary:
            return CompactResult(summary="", compacted_count=0, branch_id=active_branch, node_ids=[])
        node_ids = [node.id for node in compacted]
        self.session_manager.append_summary(session_id, branch_id=active_branch, summary=summary, node_ids=node_ids)
        return CompactResult(summary=summary, compacted_count=len(compacted), branch_id=active_branch, node_ids=node_ids)

    async def _summarize_nodes(self, nodes) -> str:
        """把一组旧节点转换成由模型生成的结构化摘要。"""

        history_text = self._build_summary_input(nodes)
        summary_model = self._resolve_summary_model()
        try:
            message = await completeSimple(
                summary_model,
                Context(
                    systemPrompt=SUMMARY_SYSTEM_PROMPT,
                    messages=[
                        UserMessage(
                            content=(
                                "请基于下面这段较早的会话历史，生成供后续继续工作的结构化摘要。\n\n"
                                f"{history_text}"
                            )
                        )
                    ],
                    tools=[],
                ),
                reasoning=self.runtime.thinking,
                registry=self.runtime.registry,
            )
        except Exception:
            return ""
        summary = str(message.content).strip()
        return summary

    def _resolve_summary_model(self) -> Model:
        """解析本次摘要生成所使用的模型。"""

        compact_model = self.runtime.settings.compact_model
        if compact_model:
            resolver = self.runtime.model_resolver
            if resolver is not None:
                return resolver.get(compact_model) if hasattr(resolver, "get") else resolver(compact_model)
        return self.runtime.model

    @staticmethod
    def _build_summary_input(nodes) -> str:
        """把一组旧节点转换成稳定的摘要输入文本。"""

        lines: list[str] = ["[较早会话历史]"]
        for node in nodes:
            if node.role == "tool":
                content = str(node.content).strip().replace("\n", " ")
                if len(content) > 240:
                    content = content[:240] + "..."
                lines.extend(
                    [
                        "- role: tool",
                        f"  tool_name: {node.tool_name or 'unknown'}",
                        f"  tool_call_id: {node.tool_call_id or ''}",
                        f"  result: {content}",
                    ]
                )
                continue

            content = str(node.content).strip().replace("\n", " ")
            if len(content) > 240:
                content = content[:240] + "..."
            lines.append(f"- role: {node.role}")
            lines.append(f"  content: {content}")
            if node.thinking:
                thinking = node.thinking.strip().replace("\n", " ")
                if len(thinking) > 240:
                    thinking = thinking[:240] + "..."
                lines.append(f"  thinking: {thinking}")
            if node.tool_calls:
                lines.append(f"  tool_calls: {node.tool_calls}")
        return "\n".join(lines)
