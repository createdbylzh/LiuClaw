from __future__ import annotations

import json
from pathlib import Path

from .types import ThemeResource


def load_themes(themes_dir: Path) -> dict[str, ThemeResource]:
    """加载主题配置，并在缺省时补上默认主题。"""

    themes: dict[str, ThemeResource] = {}
    if themes_dir.exists():
        for path in sorted(themes_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            themes[path.stem] = ThemeResource(name=path.stem, path=path, data=data)
    if "default" not in themes:
        themes["default"] = ThemeResource(
            name="default",
            path=themes_dir / "default.json",
            data={"assistant": "ansicyan", "thinking": "ansiblue", "tool": "ansiyellow", "error": "ansired"},
        )
    return themes
