from __future__ import annotations

from .compactor import SessionCompactor


def summarize_branch_on_switch(compactor: SessionCompactor, session_id: str, branch_id: str) -> str:
    """在分支切换前为旧分支生成摘要文本。"""

    result = compactor.compact_session(session_id, branch_id=branch_id)
    return result.summary
