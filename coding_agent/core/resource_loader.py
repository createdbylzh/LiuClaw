from __future__ import annotations

import json
from pathlib import Path

from .agents_context_loader import load_agents_context
from .prompts_loader import load_prompts
from .skills_loader import load_skills
from .themes_loader import load_themes
from .types import ExtensionResource, ResourceBundle


class ResourceLoader:
    """统一编排技能、提示、主题、扩展与项目上下文的加载。"""

    def __init__(
        self,
        *,
        skills_dir: Path,
        prompts_dir: Path,
        themes_dir: Path,
        extensions_dir: Path,
        workspace_root: Path,
    ) -> None:
        """保存资源目录与工作区根目录。"""

        self.skills_dir = skills_dir
        self.prompts_dir = prompts_dir
        self.themes_dir = themes_dir
        self.extensions_dir = extensions_dir
        self.workspace_root = workspace_root

    def load(self) -> ResourceBundle:
        """执行一次完整资源扫描，并返回聚合后的资源包。"""

        skills = load_skills(self.skills_dir)
        prompts = load_prompts(self.prompts_dir)
        themes = load_themes(self.themes_dir)
        agents_context = load_agents_context(self.workspace_root)
        extensions = self._scan_extensions()
        self._ensure_no_conflicts(skills, prompts, themes, extensions)
        return ResourceBundle(
            skills=skills,
            prompts=prompts,
            themes=themes,
            agents_context=agents_context,
            extensions=extensions,
        )

    def _scan_extensions(self) -> list[ExtensionResource]:
        """扫描扩展目录，仅返回描述信息而不执行扩展代码。"""

        if not self.extensions_dir.exists():
            return []
        extensions: list[ExtensionResource] = []
        for path in sorted(self.extensions_dir.iterdir()):
            if path.name.startswith("."):
                continue
            metadata: dict[str, object] = {}
            manifest = path / "extension.json" if path.is_dir() else path
            if manifest.is_file() and manifest.suffix == ".json":
                try:
                    metadata = json.loads(manifest.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    metadata = {}
            extensions.append(ExtensionResource(name=path.stem, path=path, metadata=metadata))
        return extensions

    @staticmethod
    def _ensure_no_conflicts(skills, prompts, themes, extensions) -> None:
        """检测跨资源类型的同名冲突，避免运行时歧义。"""

        seen: dict[str, str] = {}
        for kind, collection in [
            ("skill", skills),
            ("prompt", prompts.values()),
            ("theme", themes.values()),
            ("extension", extensions),
        ]:
            for item in collection:
                if item.name in seen:
                    raise ValueError(f"Resource name conflict: '{item.name}' used by {seen[item.name]} and {kind}")
                seen[item.name] = kind
