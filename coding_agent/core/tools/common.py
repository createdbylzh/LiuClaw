from __future__ import annotations

import subprocess
from pathlib import Path


def ensure_within_workspace(workspace_root: Path, target: Path) -> Path:
    """校验目标路径位于工作区内，并返回其绝对路径。"""

    root = workspace_root.resolve()
    resolved = (target if target.is_absolute() else workspace_root / target).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path escapes workspace: {resolved}") from exc
    return resolved


def truncate_text(text: str, limit: int) -> str:
    """按最大字符数截断文本，避免工具结果过大。"""

    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...<truncated {len(text) - limit} chars>"


def run_shell(command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """在指定目录执行非交互 shell 命令并捕获输出。"""

    return subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        text=True,
        capture_output=True,
        check=False,
    )
