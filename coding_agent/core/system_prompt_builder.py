from __future__ import annotations

from .system_prompt import build_system_prompt
from .types import SessionContext


class SystemPromptBuilder:
    """负责把基础系统提示与扩展附加片段拼装为最终系统提示。"""

    def build(self, context: SessionContext) -> str:
        """构造最终系统提示。"""

        prompt = build_system_prompt(context)
        if not context.extra_prompt_fragments:
            return prompt
        return "\n\n".join([prompt, *[fragment.strip() for fragment in context.extra_prompt_fragments if fragment.strip()]])
