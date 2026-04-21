from __future__ import annotations

from ai.types import Context, Model
from ai.utils.context_window import detect_context_overflow

from ..session_manager import SessionManager
from ..types import CodingAgentSettings, CompactResult, ContextStats
from .branch_summary import summarize_branch_on_switch
from .compactor import CompactionRuntime, SessionCompactor
from .triggers import should_compact


class CompactionCoordinator:
    """统一管理阈值压缩、溢出恢复、手动压缩和分支摘要。"""

    def __init__(
        self,
        session_manager: SessionManager,
        settings: CodingAgentSettings,
        *,
        model: Model,
        thinking: str | None,
        registry=None,
        model_resolver=None,
    ) -> None:
        """初始化压缩协调器，并装配内部压缩器。"""

        self.session_manager = session_manager
        self.settings = settings
        self.compactor = SessionCompactor(
            session_manager,
            CompactionRuntime(
                model=model,
                thinking=thinking,
                settings=settings,
                registry=registry,
                model_resolver=model_resolver,
            ),
        )

    async def compact_manual(self, session_ref: str, leaf_id: str | None = None, custom_instructions: str | None = None) -> CompactResult:
        """执行一次手动触发的会话压缩。"""

        return await self.compactor.compact_session(session_ref, leaf_id=leaf_id, custom_instructions=custom_instructions)

    async def maybe_compact_for_threshold(self, session_ref: str, leaf_id: str | None, model: Model, context: Context) -> CompactResult | None:
        """在发送请求前按上下文预算判断是否需要自动压缩。"""

        if not self.settings.compaction.enabled:
            return None
        report = detect_context_overflow(model, context)
        ratio = report.total_tokens / report.limit if report.limit else 0.0
        stats = ContextStats(estimated_tokens=report.total_tokens, limit=report.limit, ratio=ratio)
        if should_compact(stats, self.settings, model):
            return await self.compactor.compact_session(session_ref, leaf_id=leaf_id)
        return None

    async def recover_from_overflow(self, session_ref: str, leaf_id: str | None) -> CompactResult | None:
        """在发生上下文溢出后尝试做一次恢复性压缩。"""

        result = await self.compactor.compact_session(session_ref, leaf_id=leaf_id)
        if result.compacted_count <= 0:
            return None
        return result

    async def summarize_branch(self, session_ref: str, old_leaf_id: str | None, target_leaf_id: str | None) -> str:
        """在分支切换时为离开的路径生成摘要。"""

        return await summarize_branch_on_switch(self.compactor, session_ref, old_leaf_id, target_leaf_id)
