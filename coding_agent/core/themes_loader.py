from __future__ import annotations

import json
from pathlib import Path

from .types import ThemeResource


DEFAULT_THEME_DATA = {
    "user": "ansimagenta bold",
    "assistant_header": "ansicyan bold",
    "assistant_body": "ansicyan",
    "thinking_header": "ansiblue bold",
    "thinking_body": "ansiblue",
    "tool_header": "ansiyellow bold",
    "tool_running": "ansiyellow",
    "tool_success": "ansigreen",
    "tool_error": "ansired",
    "status": "ansiwhite",
    "error": "ansired bold",
    "status_bar": "reverse",
    "input_prompt": "ansimagenta",
}


def load_themes(themes_dir: Path) -> dict[str, ThemeResource]:
    """加载主题配置，并在缺省时补上默认主题。"""

    themes: dict[str, ThemeResource] = {}
    if themes_dir.exists():
        for path in sorted(themes_dir.glob("*.json")):
            data = dict(DEFAULT_THEME_DATA)
            data.update(json.loads(path.read_text(encoding="utf-8")))
            themes[path.stem] = ThemeResource(name=path.stem, path=path, data=data)
    if "default" not in themes:
        themes["default"] = ThemeResource(
            name="default",
            path=themes_dir / "default.json",
            data=dict(DEFAULT_THEME_DATA),
        )
    return themes
