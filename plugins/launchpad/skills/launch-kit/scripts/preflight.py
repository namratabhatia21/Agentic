#!/usr/bin/env python3
"""Pre-launch checks for a Claude Code skill, plugin or marketplace repository.

Usage: python3 preflight.py [PATH] [--strict]

PATH can be a skill folder (has SKILL.md), a plugin (has .claude-plugin/plugin.json) or a
repository / marketplace (has .claude-plugin/marketplace.json). Every SKILL.md, plugin and
marketplace under PATH is checked. Standard library only, so it runs anywhere Python 3.11+
does.

`claude plugin validate` stays the authority on plugin manifests. This script adds what it
doesn't cover: portability to other agents, description quality, broken links inside a
skill, and the things that make people install it (README, install command, demo, license).
Exit code is 1 when there are errors, or warnings with --strict.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NAME_MAX = 64
SPEC_DESCRIPTION_MAX = 1024  # Agent Skills spec (agentskills.io)
CLAUDE_CODE_LISTING_MAX = 1536  # Claude Code: description + when_to_use
DESCRIPTION_MIN = 80
BODY_LINES_MAX = 500
# Frontmatter Claude Code understands but claude.ai uploads, the Skills API and other agents reject.
CLAUDE_CODE_ONLY = {
    "agent",
    "argument-hint",
    "arguments",
    "background",
    "context",
    "disable-model-invocation",
    "effort",
    "hooks",
    "model",
    "paths",
    "shell",
    "user-invocable",
    "when_to_use",
}
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache"}
INSTALL_HINTS = ("plugin install", "plugin marketplace add", "skills add", ".claude/skills")
MEDIA_RE = re.compile(r"!\[|<img|<video|\.(gif|mp4|webm|mov)\b", re.IGNORECASE)
TRIGGER_RE = re.compile(r"\b(when|whenever|use (it |this )?(for|to|on))\b", re.IGNORECASE)
LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
FENCE_RE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
BLOCK_SCALARS = {"|", ">", "|-", ">-", "|+", ">+"}


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=lambda: {"skill": 0, "plugin": 0, "market": 0})

    def error(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"{where}: {msg}")


def parse_frontmatter(text: str) -> tuple[dict[str, str] | None, str]:
    """Split a SKILL.md into (frontmatter, body).

    Reads the flat `key: value` YAML that skills use. Indented lines, list items and
    block scalars are folded into the preceding key's value as one line of text.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None, text

    meta: dict[str, str] = {}
    key = None
    for raw in lines[1:end]:
        if not raw.strip() or raw.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", raw)
        if match:
            key, value = match.group(1), match.group(2).strip()
            meta[key] = "" if value in BLOCK_SCALARS else _unquote(value)
        elif key is not None:
            meta[key] = f"{meta[key]} {raw.strip()}".strip()
    return meta, "\n".join(lines[end + 1 :])


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)) or "."
    except ValueError:
        return str(path)


def _load_json(path: Path, report: Report, root: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.error(_rel(path, root), f"invalid JSON: {exc}")
        return None
    if not isinstance(data, dict):
        report.error(_rel(path, root), "must be a JSON object")
        return None
    return data


def _check_name(name: object, where: str, what: str, report: Report) -> bool:
    if not name:
        report.error(where, f"missing `name` for the {what}")
        return False
    if not isinstance(name, str) or len(name) > NAME_MAX or not NAME_RE.fullmatch(name):
        report.error(
            where,
            f"{what} name {name!r} must be kebab-case (lowercase letters, digits, single "
            f"hyphens) and at most {NAME_MAX} characters",
        )
        return False
    return True


def check_skill(skill_md: Path, root: Path, report: Report) -> None:
    report.counts["skill"] += 1
    where = _rel(skill_md, root)
    meta, body = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    if meta is None:
        report.error(where, "no YAML frontmatter; start the file with --- name / description ---")
        return

    name = meta.get("name", "")
    folder = skill_md.parent.name
    if _check_name(name, where, "skill", report) and name != folder:
        report.warn(
            where,
            f"name {name!r} differs from its folder {folder!r}; the Agent Skills spec "
            "requires them to match, and `npx skills add` installs by folder",
        )

    description = meta.get("description", "")
    listing = len(description) + len(meta.get("when_to_use", ""))
    if not description:
        report.error(where, "missing `description`; it is how Claude decides to use the skill")
    else:
        if listing > CLAUDE_CODE_LISTING_MAX:
            report.error(
                where,
                f"description + when_to_use is {listing} characters; Claude Code drops "
                f"listings over {CLAUDE_CODE_LISTING_MAX}",
            )
        elif len(description) > SPEC_DESCRIPTION_MAX:
            report.warn(
                where,
                f"description is {len(description)} characters; the Agent Skills spec and "
                f"other agents allow {SPEC_DESCRIPTION_MAX}",
            )
        if len(description) < DESCRIPTION_MIN:
            report.warn(where, "description is very short; say what it does and when to use it")
        if not TRIGGER_RE.search(description + " " + meta.get("when_to_use", "")):
            report.warn(
                where,
                "description never says when to use the skill; add 'Use when ...' with the "
                "words people type",
            )

    claude_only = sorted(CLAUDE_CODE_ONLY & meta.keys())
    if claude_only:
        report.warn(
            where,
            f"Claude Code-only frontmatter ({', '.join(claude_only)}): fine in Claude Code, "
            "rejected by claude.ai uploads, the Skills API and other agents",
        )

    body_lines = len(body.splitlines())
    if body_lines > BODY_LINES_MAX:
        report.warn(
            where,
            f"{body_lines} lines; keep SKILL.md under {BODY_LINES_MAX} and move details to "
            "reference files it links to",
        )

    for target in LINK_RE.findall(FENCE_RE.sub("", body)):
        if "://" in target or "$" in target or target.startswith(("#", "mailto:")):
            continue
        path = target.split("#", 1)[0]
        if path and not (skill_md.parent / path).exists():
            report.error(where, f"links to {path}, which doesn't exist")


def check_plugin(plugin_dir: Path, root: Path, report: Report) -> str | None:
    report.counts["plugin"] += 1
    manifest = plugin_dir / ".claude-plugin" / "plugin.json"
    where = _rel(manifest, root)
    data = _load_json(manifest, report, root)
    if data is None:
        return None

    name = data.get("name")
    _check_name(name, where, "plugin", report)
    if not data.get("description"):
        report.warn(where, "no `description`; it is the line people see in /plugin")
    if not data.get("author"):
        report.warn(where, "no `author`")
    if not (data.get("homepage") or data.get("repository")):
        report.warn(where, "no `homepage` or `repository`; people can't find the source")

    for misplaced in ("skills", "agents", "commands", "hooks"):
        if (plugin_dir / ".claude-plugin" / misplaced).exists():
            report.error(
                where,
                f"{misplaced}/ is inside .claude-plugin/ and won't load; move it to the "
                "plugin root",
            )
    if not any(plugin_dir.rglob("SKILL.md")):
        report.warn(_rel(plugin_dir, root), "plugin ships no skills")
    if plugin_dir != root and not (plugin_dir / "README.md").exists():
        report.warn(_rel(plugin_dir, root), "no README.md at the plugin root")
    return name if isinstance(name, str) else None


def check_marketplace(market_dir: Path, root: Path, report: Report) -> None:
    report.counts["market"] += 1
    manifest = market_dir / ".claude-plugin" / "marketplace.json"
    where = _rel(manifest, root)
    data = _load_json(manifest, report, root)
    if data is None:
        return

    _check_name(data.get("name"), where, "marketplace", report)
    owner = data.get("owner")
    if not (isinstance(owner, dict) and owner.get("name")):
        report.error(where, "missing `owner.name`")
    plugins = data.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        report.error(where, "`plugins` must be a non-empty list")
        return

    for i, entry in enumerate(plugins):
        at = f"{where} plugins[{i}]"
        if not isinstance(entry, dict):
            report.error(at, "must be an object")
            continue
        entry_name = entry.get("name")
        _check_name(entry_name, at, "plugin entry", report)
        source = entry.get("source")
        if not source:
            report.error(at, "missing `source`")
            continue
        if not isinstance(source, str):
            continue  # github / git-subdir / url sources are fetched at install time
        if ".." in Path(source).parts:
            report.error(at, f"source {source!r} contains '..'; write it from the marketplace root")
            continue
        plugin_dir = market_dir / source
        if not plugin_dir.is_dir():
            report.error(at, f"source {source!r} doesn't exist; install will fail")
            continue
        plugin_json = plugin_dir / ".claude-plugin" / "plugin.json"
        if plugin_json.exists():
            manifest_name = (_load_json(plugin_json, Report(), root) or {}).get("name")
            if manifest_name and manifest_name != entry_name:
                report.error(
                    at,
                    f"entry name {entry_name!r} differs from plugin.json name "
                    f"{manifest_name!r}; installing by name will fail",
                )


def check_repo(root: Path, report: Report) -> None:
    """What a visitor to the repo page needs before they'll install anything."""
    readme = root / "README.md"
    if not readme.exists():
        report.warn(".", "no README.md; it is the landing page people judge the skill by")
        return
    text = readme.read_text(encoding="utf-8")
    if not any(hint in text for hint in INSTALL_HINTS):
        report.warn(
            "README.md",
            "no install command; add `claude plugin install ...` or `npx skills add ...`",
        )
    if not MEDIA_RE.search(text):
        report.warn(
            "README.md", "no demo GIF, image or video; show the result before explaining it"
        )
    if not any(root.glob("LICENSE*")) and not any(root.glob("LICENCE*")):
        report.warn(".", "no LICENSE file; many people and companies can't use unlicensed code")


def _walk(root: Path):
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        yield Path(current), files


def run(path: Path) -> Report:
    root = path.resolve()
    report = Report()
    if root.is_file() and root.name == "SKILL.md":
        check_skill(root, root.parent, report)
        return report
    if not root.is_dir():
        report.error(str(path), "not a directory or SKILL.md")
        return report

    for current, files in _walk(root):
        manifest_dir = current / ".claude-plugin"
        if (manifest_dir / "marketplace.json").is_file():
            check_marketplace(current, root, report)
        if (manifest_dir / "plugin.json").is_file():
            check_plugin(current, root, report)
        if "SKILL.md" in files:
            check_skill(current / "SKILL.md", root, report)

    if not any(report.counts.values()):
        report.error(str(path), "no SKILL.md, plugin.json or marketplace.json found")
    elif (
        (root / ".git").exists()
        or (root / ".claude-plugin").is_dir()
        or (root / "README.md").exists()
    ):
        check_repo(root, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", nargs="?", default=".", help="skill, plugin or repo folder")
    parser.add_argument("--strict", action="store_true", help="fail on warnings too")
    args = parser.parse_args(argv)

    report = run(Path(args.path))
    c = report.counts
    print(
        f"Preflight {args.path}: {c['market']} marketplace(s), {c['plugin']} plugin(s), "
        f"{c['skill']} skill(s)"
    )
    for line in report.errors:
        print(f"  ERROR {line}")
    for line in report.warnings:
        print(f"  WARN  {line}")
    failed = bool(report.errors) or (args.strict and bool(report.warnings))
    verdict = "fix the issues above before launching" if failed else "ready to launch"
    print(f"{len(report.errors)} error(s), {len(report.warnings)} warning(s): {verdict}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
