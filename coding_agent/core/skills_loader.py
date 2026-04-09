from __future__ import annotations

from pathlib import Path
import re

from .types import SkillResource


_FRONTMATTER_DELIMITER = "---"


def _split_frontmatter(content: str) -> tuple[str | None, str]:
    text = content.lstrip()
    if not text.startswith(f"{_FRONTMATTER_DELIMITER}\n"):
        return None, content
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIMITER:
        return None, content
    for index in range(1, len(lines)):
        if lines[index].strip() == _FRONTMATTER_DELIMITER:
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1 :])
    return None, content


def _parse_frontmatter(frontmatter: str | None) -> dict[str, str]:
    if frontmatter is None:
        return {}
    parsed: dict[str, str] = {}
    for raw_line in frontmatter.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        parsed[key.strip()] = value.strip().strip("\"'")
    return parsed


def load_skills(skills_dir: Path) -> list[SkillResource]:
    """扫描技能目录并加载全部符合规范的 `SKILL.md` 摘要。"""

    if not skills_dir.exists():
        return []
    skills: list[SkillResource] = []
    for path in sorted(skills_dir.rglob("SKILL.md")):
        content = path.read_text(encoding="utf-8")
        metadata = _parse_frontmatter(_split_frontmatter(content)[0])
        name = metadata.get("name", "").strip()
        description = metadata.get("description", "").strip()
        if not name or not description:
            continue
        if path.parent != skills_dir and name != path.parent.name:
            continue
        if not re.fullmatch(r"[a-z0-9-]+", name):
            continue
        skills.append(SkillResource(name=name, description=description, path=path))
    return skills
