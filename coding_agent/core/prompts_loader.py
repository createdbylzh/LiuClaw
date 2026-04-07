from __future__ import annotations

from pathlib import Path

from .types import PromptResource

DEFAULT_SYSTEM_PROMPT = """你是 LiuClaw Coding Agent，一个可扩展的终端编码助手。

始终优先：
1. 理解当前仓库与用户目标
2. 以安全、最小必要修改完成任务
3. 清晰汇报工具动作与结果
4. 当信息不足时基于当前环境做合理假设
"""


def load_prompts(prompts_dir: Path) -> dict[str, PromptResource]:
    """加载提示模板目录，并确保提供默认 `SYSTEM` 提示。"""

    prompts: dict[str, PromptResource] = {}
    if prompts_dir.exists():
        for path in sorted(prompts_dir.glob("*.md")):
            prompts[path.stem] = PromptResource(name=path.stem, path=path, content=path.read_text(encoding="utf-8"))
    if "SYSTEM" not in prompts:
        prompts["SYSTEM"] = PromptResource(name="SYSTEM", path=prompts_dir / "SYSTEM.md", content=DEFAULT_SYSTEM_PROMPT)
    return prompts
