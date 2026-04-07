from __future__ import annotations

from ai.types import Model

from ..types import CodingAgentSettings, ContextStats


def should_compact(context_stats: ContextStats, settings: CodingAgentSettings, model: Model) -> bool:
    """根据上下文占用比例与设置判断是否触发压缩。"""

    if not settings.auto_compact:
        return False
    return context_stats.ratio >= settings.compact_threshold or context_stats.estimated_tokens >= model.contextWindow
