import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "plugins/launchpad/skills/launch-kit/scripts/preflight.py"

spec = importlib.util.spec_from_file_location("preflight", SCRIPT)
preflight = importlib.util.module_from_spec(spec)
sys.modules["preflight"] = preflight  # dataclasses look the module up while it loads
spec.loader.exec_module(preflight)

GOOD_DESCRIPTION = (
    "Writes conventional commit messages from the staged diff. Use when the user asks for "
    "a commit message or says 'commit this'."
)


def write_skill(folder: Path, frontmatter: str, body: str = "Do the thing.\n") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    skill_md = folder / "SKILL.md"
    skill_md.write_text(f"---\n{frontmatter}\n---\n\n{body}", encoding="utf-8")
    return skill_md


def test_bundled_plugin_and_marketplace_have_no_errors():
    report = preflight.run(REPO)
    assert report.errors == []
    assert report.counts == {"skill": 1, "plugin": 1, "market": 1}


def test_good_skill_passes_clean(tmp_path):
    write_skill(tmp_path / "commit-msg", f"name: commit-msg\ndescription: {GOOD_DESCRIPTION}")
    report = preflight.run(tmp_path / "commit-msg")
    assert report.errors == [] and report.warnings == []


@pytest.mark.parametrize(
    "frontmatter,expected",
    [
        ("description: x", "missing `name`"),
        (f"name: Commit_Msg\ndescription: {GOOD_DESCRIPTION}", "must be kebab-case"),
        ("name: commit-msg", "missing `description`"),
        (f"name: commit-msg\ndescription: {'a' * 1600}", "Claude Code drops listings"),
    ],
)
def test_skill_errors(tmp_path, frontmatter, expected):
    write_skill(tmp_path / "commit-msg", frontmatter)
    report = preflight.run(tmp_path / "commit-msg")
    assert any(expected in e for e in report.errors), report.errors


def test_missing_frontmatter_and_broken_link(tmp_path):
    folder = tmp_path / "a"
    folder.mkdir()
    (folder / "SKILL.md").write_text("Just text\n", encoding="utf-8")
    write_skill(
        tmp_path / "b",
        f"name: b\ndescription: {GOOD_DESCRIPTION}",
        "See [ref](reference.md) and [docs](https://example.com).\n"
        "```\n[not a link](missing.md)\n```\n",
    )
    errors = preflight.run(tmp_path).errors
    assert any("no YAML frontmatter" in e for e in errors)
    assert [e for e in errors if "doesn't exist" in e] == [
        f"{Path('b/SKILL.md')}: links to reference.md, which doesn't exist"
    ]


def test_warnings_for_vague_or_non_portable_skill(tmp_path):
    write_skill(
        tmp_path / "helper",
        "name: other-name\ndescription: >\n  Helps with git\ndisable-model-invocation: true",
    )
    warnings = " ".join(preflight.run(tmp_path / "helper").warnings)
    assert "differs from its folder" in warnings
    assert "very short" in warnings
    assert "never says when to use" in warnings
    assert "Claude Code-only frontmatter (disable-model-invocation)" in warnings


def test_marketplace_entry_must_match_plugin_name(tmp_path):
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / ".claude-plugin/marketplace.json").write_text(
        json.dumps(
            {
                "name": "shop",
                "owner": {"name": "Me"},
                "plugins": [
                    {"name": "tool", "source": "./plugins/tool"},
                    {"name": "gone", "source": "./plugins/gone"},
                    {"name": "up", "source": "../up"},
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "plugins/tool/.claude-plugin/plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"name": "tool-renamed"}), encoding="utf-8")
    errors = " ".join(preflight.run(tmp_path).errors)
    assert "differs from plugin.json name 'tool-renamed'" in errors
    assert "'./plugins/gone' doesn't exist" in errors
    assert "contains '..'" in errors


def test_cli_exit_codes(tmp_path, capsys):
    write_skill(tmp_path / "s", "name: s\ndescription: Helps with git")
    assert preflight.main([str(tmp_path / "s")]) == 0
    assert preflight.main([str(tmp_path / "s"), "--strict"]) == 1
    assert preflight.main([str(tmp_path / "nothing-here")]) == 1
    assert "error(s)" in capsys.readouterr().out
