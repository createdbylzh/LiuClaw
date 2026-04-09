from __future__ import annotations

import subprocess
from pathlib import Path


def resolve_path(cwd: Path, target: Path) -> Path:
    """把绝对路径原样返回，相对路径按当前 cwd 解析。"""

    return (target if target.is_absolute() else cwd / target).resolve()


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
