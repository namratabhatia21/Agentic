import copy
import csv
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parent.parent / "plugins/coursecraft/skills/course-builder"
EXAMPLE = SKILL / "assets/example-course/course.json"

spec = importlib.util.spec_from_file_location("course_tool", SKILL / "scripts/course_tool.py")
course_tool = importlib.util.module_from_spec(spec)
sys.modules["course_tool"] = course_tool  # dataclasses look the module up while it loads
spec.loader.exec_module(course_tool)


def example() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def check(data: dict, tmp_path: Path, final: bool = False):
    path = tmp_path / "course.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return course_tool.check(course_tool.load(path), final=final)


def joined(lines: list[str]) -> str:
    return "\n".join(lines)


def test_example_course_passes_final_check():
    report = course_tool.check(course_tool.load(EXAMPLE), final=True)
    assert report.errors == [] and report.warnings == []
    assert "6 assessment items" in report.info[0]


@pytest.mark.parametrize(
    "text,verb",
    [
        ("Explain how context changes an answer", "explain"),
        ("Learners will be able to diagnose a failed prompt", "diagnose"),
        ("By the end of this module, you will analyse the data", "analyze"),
        ("Summarise the report", "summarize"),
        ("Be aware of phishing risks", "be aware"),
    ],
)
def test_leading_verb(text, verb):
    assert course_tool.leading_verb(text) == verb


def test_objective_quality(tmp_path):
    data = example()
    objectives = data["modules"][0]["objectives"]
    objectives[0]["text"] = "Understand the four parts of a prompt"
    objectives[1]["text"] = "List the ways context changes an answer"  # remember verb
    objectives[1]["bloom"] = "analyze"
    data["outcomes"][1]["text"] = "Critique prompts and recommend fixes"
    report = check(data, tmp_path)
    assert "M1.1: 'understand' can't be observed or measured" in joined(report.errors)
    assert "M1.2: 'list' is a remember verb but bloom is 'analyze'" in joined(report.warnings)
    assert "CO2: two verbs in one objective" in joined(report.warnings)


def test_alignment_errors(tmp_path):
    data = example()
    m1 = data["modules"][0]
    m1["objectives"].append(
        {"id": "M1.3", "text": "Name three assistants", "bloom": "remember", "supports": ["CO9"]}
    )
    m1["lessons"][0]["objectives"].append("M9.9")
    m1["assessment"][0]["objective"] = "M1.2"  # M1.1 is now never assessed
    m1["lessons"].append(copy.deepcopy(m1["lessons"][0]))  # duplicate id
    errors = joined(check(data, tmp_path).errors)
    assert "M1.3: supports unknown outcome CO9" in errors
    assert "M1.3: not taught in any lesson or activity" in errors
    assert "M1.3: not assessed" in errors
    assert "M1.1: not assessed" in errors
    assert "M1.L1: refers to unknown objective M9.9" in errors
    assert "M1.L1: duplicate id" in errors


def test_level_mismatch_practice_and_time(tmp_path):
    data = example()
    m2 = data["modules"][1]
    m2["assessment"][1]["bloom"] = "remember"  # M2.2 is analyze
    m2["activities"] = [a for a in m2["activities"] if a["id"] != "M2.A3"]
    m2["lessons"][0]["minutes"] = 25
    warnings = joined(check(data, tmp_path).warnings)
    assert "M2.Q2: assesses at 'remember' but M2.2 is 'analyze'" in warnings
    assert "M2.4: 'create' objective has no practice activity" in warnings
    assert "M2.L1: 25 min; split lessons" in warnings


def test_item_quality(tmp_path):
    data = example()
    items = data["modules"][0]["assessment"]
    items[0]["answer"] = 7
    items[1]["options"][3] = "All of the above"
    items[1]["stem"] = "Which of these is NOT a reason?"
    items[2]["answer"] = "yes"
    report = check(data, tmp_path)
    assert "M1.Q1: answer must be option index(es) 0-3" in joined(report.errors)
    assert "M1.Q3: truefalse answer must be true or false" in joined(report.errors)
    assert "M1.Q2: avoid 'all/none of the above'" in joined(report.warnings)
    assert "M1.Q2: negative stem" in joined(report.warnings)


def test_answer_key_patterns(tmp_path):
    data = example()
    template = data["modules"][0]["assessment"][0]
    items = []
    for i in range(7):
        item = copy.deepcopy(template)
        item["id"] = f"M1.X{i}"
        item["options"] = ["a", "b", "c", "the correct and much longer option"]
        item["answer"] = 3
        items.append(item)
    data["modules"][0]["assessment"] += items
    warnings = joined(check(data, tmp_path).warnings)
    assert "same position" in warnings
    assert "usually the longest" in warnings


def test_final_requires_content_and_flags_gaps(tmp_path):
    data = example()
    del data["modules"][0]["lessons"][0]["file"]
    (tmp_path / "lesson.md").write_text("# L\n\n[GAP: need the 2024 figures]\n", encoding="utf-8")
    data["modules"][0]["lessons"][1]["file"] = "lesson.md"
    data["modules"][1]["lessons"][0]["file"] = "missing.md"
    draft = check(data, tmp_path)
    assert "M1.L1" not in joined(draft.errors)
    assert "M2.L1: content file missing.md doesn't exist" in joined(draft.errors)
    final = check(data, tmp_path, final=True)
    assert "M1.L1: no content file" in joined(final.errors)
    assert "1 unresolved [GAP]" in joined(final.warnings)


def test_matrix_lists_every_objective():
    text = course_tool.matrix(course_tool.load(EXAMPLE))
    assert "| Outcome | Objective | Bloom | Taught in | Practised in | Assessed by |" in text
    assert "| CO1 | **M2.4** Design a reusable prompt template" in text
    assert "| M2.L1 | M2.A3 | F1 |" in text


def test_gift_export():
    gift = course_tool.export_gift(course_tool.load(EXAMPLE))
    assert "$CATEGORY: $course$/top/Write Better Prompts for AI Assistants/Final assessment" in gift
    assert "::M1.Q1::Which part of a prompt" in gift
    assert "  =Format #Right." in gift
    assert "like this\\: [paste]" in gift  # colon escaped
    assert "{TRUE#" in gift
    assert "::F1::Choose a task" in gift and gift.count("{}") == 1


def test_gift_multi_weights(tmp_path):
    data = example()
    data["modules"][0]["assessment"] = [
        {
            "id": "Q",
            "type": "multi",
            "objective": "M1.1",
            "bloom": "remember",
            "stem": "Select all parts of a prompt",
            "options": ["Task", "Context", "Mood", "Format"],
            "answer": [0, 1, 3],
        }
    ]
    path = tmp_path / "course.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    gift = course_tool.export_gift(course_tool.load(path))
    assert "~%33.33333%Task" in gift and "~%-100%Mood" in gift


def test_aiken_and_csv_exports():
    course = course_tool.load(EXAMPLE)
    aiken, skipped = course_tool.export_aiken(course)
    assert skipped == 2  # the true/false item and the project
    assert aiken.count("ANSWER:") == 4 and "D. Examples\nANSWER: C" in aiken
    rows = list(csv.DictReader(io.StringIO(course_tool.export_csv(course))))
    assert len(rows) == 6
    assert rows[0]["correct"] == "Format" and rows[0]["module"] == "M1"
    assert rows[2]["correct"] == "true"


def test_markdown_renderer():
    out = course_tool.markdown_to_html(
        "## Head\n\nSome **bold** and *em* and `code` <b>.\n\n- one\n- two\n\n"
        "| A | B |\n|---|---|\n| 1 | 2 |\n\n> quoted\n\n```\nx < 1\n```\n"
    )
    assert "<h2>Head</h2>" in out
    assert "<strong>bold</strong> and <em>em</em> and <code>code</code> &lt;b&gt;." in out
    assert "<ul><li>one</li><li>two</li></ul>" in out
    assert "<td>1</td><td>2</td>" in out
    assert "<blockquote><p>quoted</p></blockquote>" in out
    assert "<pre><code>x &lt; 1</code></pre>" in out


def test_preview_embeds_lessons_safely(tmp_path):
    data = example()
    data["title"] = "Course </script><script>alert(1)</script>"
    path = tmp_path / "course.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    for lesson in (m for mod in data["modules"] for m in mod["lessons"]):
        target = tmp_path / lesson["file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((EXAMPLE.parent / lesson["file"]).read_text(), encoding="utf-8")
    page = course_tool.preview(course_tool.load(path))
    assert page.count("</script>") == 2  # only the two real closing tags
    assert "<title>Course &lt;/script&gt;" in page
    assert "<h2>The four parts<\\/h2>" in page  # lesson HTML sits in escaped JSON
    assert "# The anatomy of a prompt" not in page


def test_cli(tmp_path, capsys):
    assert course_tool.main(["check", str(EXAMPLE), "--final"]) == 0
    out = tmp_path / "out/quiz.gift"
    assert course_tool.main(["export", str(EXAMPLE), "--format", "gift", "--out", str(out)]) == 0
    assert out.read_text().startswith("$CATEGORY")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert course_tool.main(["check", str(bad)]) == 1
    assert "0 error(s), 0 warning(s)" in capsys.readouterr().out
