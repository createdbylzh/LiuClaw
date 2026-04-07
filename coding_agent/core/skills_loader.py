from __future__ import annotations

from pathlib import Path

from .types import SkillResource


def load_skills(skills_dir: Path) -> list[SkillResource]:
    """扫描技能目录并加载全部 `SKILL.md` 文件。"""

    if not skills_dir.exists():
        return []
    skills: list[SkillResource] = []
    for path in sorted(skills_dir.rglob("SKILL.md")):
        name = path.parent.name if path.parent != skills_dir else path.stem
        skills.append(SkillResource(name=name, path=path, content=path.read_text(encoding="utf-8")))
    return skills
