from __future__ import annotations

from pathlib import Path


def load_agents_context(workspace_root: Path) -> str | None:
    """从当前工作区向上查找最近的 `AGENTS.md`。"""

    current = workspace_root.resolve()
    for candidate in [current, *current.parents]:
        path = candidate / "AGENTS.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
    return None
