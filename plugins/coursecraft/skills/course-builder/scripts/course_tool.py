#!/usr/bin/env python3
"""Check, map, export and preview a course blueprint (course.json).

Usage:
  python3 course_tool.py check   course.json [--final]
  python3 course_tool.py matrix  course.json [--out FILE]
  python3 course_tool.py export  course.json --format gift|aiken|csv [--out FILE]
  python3 course_tool.py preview course.json [--out FILE]

check    Bloom's taxonomy and alignment QA: measurable objectives, verb vs. declared level,
         every objective taught, practised and assessed at the right level, outcome coverage,
         lesson length, quiz item quality. --final also requires every lesson's content file
         and fails on warnings.
matrix   Markdown alignment matrix: outcome -> objective -> lessons -> activities -> items.
export   Quiz items for an LMS: Moodle GIFT, Aiken (single-answer MCQ only) or CSV.
preview  One self-contained HTML file to click through the course and take the quizzes.

Standard library only (Python 3.11+). The blueprint format is in references/course-json.md.
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

LEVELS = ["remember", "understand", "apply", "analyze", "evaluate", "create"]
RANK = {level: i for i, level in enumerate(LEVELS)}
# Revised Bloom's taxonomy (Anderson & Krathwohl, 2001). Some verbs sit at two levels; the
# declared level decides, the verb only has to be compatible with it.
VERBS = {
    "remember": "define duplicate identify label list locate match memorize name outline quote "
    "recall recite recognize record repeat reproduce retrieve select state describe",
    "understand": "classify compare contrast convert describe discuss distinguish estimate "
    "exemplify explain extend generalize give illustrate infer interpret paraphrase predict "
    "rephrase summarize translate",
    "apply": "apply calculate carry change compute construct demonstrate employ execute "
    "implement modify operate perform prepare produce rewrite schedule sketch solve use "
    # Observable workplace procedures, common in compliance and onboarding courses.
    "complete configure follow install navigate report respond submit",
    "analyze": "analyze attribute break categorize compare contrast deconstruct diagnose "
    "differentiate discriminate dissect distinguish examine experiment investigate organize "
    "outline question relate structure test troubleshoot",
    "evaluate": "appraise argue assess check choose conclude critique debate decide defend "
    "determine evaluate judge justify measure prioritize rank rate recommend select support "
    "validate verify",
    "create": "assemble build compose construct create design develop devise formulate "
    "generate hypothesize invent plan produce propose write",
}
VERB_LEVELS: dict[str, set[str]] = {}
for _level, _words in VERBS.items():
    for _verb in _words.split():
        VERB_LEVELS.setdefault(_verb, set()).add(_level)
VAGUE_VERBS = {
    "understand", "know", "learn", "appreciate", "comprehend", "grasp", "realize", "believe",
    "master", "familiarize", "internalize", "explore", "value", "see",
}  # fmt: skip
VAGUE_PHRASES = ("be aware", "become aware", "be familiar", "become familiar", "gain", "have")
PREFIX_RE = re.compile(
    r"^(?:by the end of [^,]*,\s*)?"
    r"(?:(?:learners|students|participants|you|they|the learner|the student)\s+)?"
    r"(?:will\s+)?(?:be\s+able\s+to\s+)?",
    re.IGNORECASE,
)
ITEM_TYPES = {"mcq", "multi", "truefalse", "short", "essay", "project"}
CHOICE_TYPES = {"mcq", "multi"}
LESSON_MAX_MINUTES = 15
LOWER_ORDER_MAX_SHARE = 0.6
DURATION_TOLERANCE = 0.25
TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "preview-template.html"


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    def error(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"{where}: {msg}")


@dataclass
class Course:
    """A course.json flattened into lookups, so checks don't re-walk the tree."""

    data: dict
    base: Path
    outcomes: list[dict]
    modules: list[dict]
    objectives: list[dict]
    lessons: list[dict]
    activities: list[dict]
    items: list[dict]
    module_of: dict[str, str]


def load(path: Path) -> Course:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("course.json must be a JSON object")
    modules = [m for m in data.get("modules", []) if isinstance(m, dict)]
    module_of: dict[str, str] = {}
    objectives, lessons, activities, items = [], [], [], []
    for module in modules:
        mid = module.get("id", "?")
        for key, bucket in (
            ("objectives", objectives),
            ("lessons", lessons),
            ("activities", activities),
            ("assessment", items),
        ):
            for entry in module.get(key, []):
                if isinstance(entry, dict):
                    bucket.append(entry)
                    module_of[str(entry.get("id"))] = mid
    for entry in data.get("final_assessment", []):
        if isinstance(entry, dict):
            items.append(entry)
            module_of[str(entry.get("id"))] = "final"
    outcomes = [o for o in data.get("outcomes", []) if isinstance(o, dict)]
    return Course(
        data, path.parent, outcomes, modules, objectives, lessons, activities, items, module_of
    )


def refs(entry: dict, key: str = "objectives") -> list[str]:
    """IDs an entry points at. Accepts "objective": "M1.1" or "objectives": [...]."""
    value = entry.get(key, entry.get(key.rstrip("s"), []))
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value] if isinstance(value, list) else []


def leading_verb(text: str) -> str:
    rest = PREFIX_RE.sub("", text.strip()).lower()
    for phrase in VAGUE_PHRASES:
        if rest.startswith(phrase + " "):
            return phrase
    match = re.match(r"[a-z]+", rest)
    return normalize_verb(match.group(0)) if match else ""


def normalize_verb(verb: str) -> str:
    """British spellings (analyse, summarise) to the forms in VERBS."""
    for uk, us in (("yse", "yze"), ("ise", "ize")):
        if verb.endswith(uk) and verb[: -len(uk)] + us in VERB_LEVELS:
            return verb[: -len(uk)] + us
    return verb


def level(entry: dict) -> str:
    return str(entry.get("bloom", "")).strip().lower()


# --------------------------------------------------------------------------- check


def check(course: Course, final: bool = False) -> Report:
    report = Report()
    _check_ids(course, report)
    _check_outcomes(course, report)
    _check_objectives(course, report)
    _check_alignment(course, report)
    _check_items(course, report)
    _check_time(course, report)
    _check_content(course, report, final)
    _summarize(course, report)
    return report


def _check_ids(course: Course, report: Report) -> None:
    seen: set[str] = set()
    every = (
        course.outcomes
        + course.modules
        + course.objectives
        + course.lessons
        + course.activities
        + course.items
    )
    for entry in every:
        eid = entry.get("id")
        if not eid:
            report.error(str(entry.get("title") or entry.get("text") or entry)[:40], "missing id")
        elif str(eid) in seen:
            report.error(str(eid), "duplicate id")
        else:
            seen.add(str(eid))
    if not course.data.get("title"):
        report.error("course", "missing title")
    if not course.outcomes:
        report.error("course", "no course outcomes; start Design by writing 2-6 of them")
    if not course.modules:
        report.error("course", "no modules")


def _check_objective_text(where: str, entry: dict, report: Report) -> None:
    text = str(entry.get("text", "")).strip()
    declared = level(entry)
    if not text:
        report.error(where, "missing text")
        return
    if declared not in RANK:
        report.error(where, f"bloom {entry.get('bloom')!r} is not one of {', '.join(LEVELS)}")
    verb = leading_verb(text)
    if verb in VAGUE_VERBS or verb in VAGUE_PHRASES:
        report.error(
            where,
            f"'{verb}' can't be observed or measured; start with a Bloom verb "
            "(see references/blooms.md)",
        )
        return
    verb_levels = VERB_LEVELS.get(verb)
    if verb_levels is None:
        report.warn(where, f"'{verb}' isn't in the Bloom verb list; check it is observable")
    elif declared in RANK and declared not in verb_levels:
        expected = " or ".join(sorted(verb_levels, key=RANK.get))
        report.warn(where, f"'{verb}' is a {expected} verb but bloom is '{declared}'")
    rest = text.lower().split(verb, 1)[-1] if verb else ""
    second = re.search(r"\band\s+([a-z]+)", rest)
    if second and normalize_verb(second.group(1)) in VERB_LEVELS:
        report.warn(where, "two verbs in one objective; split it so each can be assessed")


def _check_outcomes(course: Course, report: Report) -> None:
    supported: dict[str, list[dict]] = {str(o.get("id")): [] for o in course.outcomes}
    for obj in course.objectives:
        links = refs(obj, "supports")
        if not links:
            report.warn(str(obj.get("id")), "not linked to a course outcome (`supports`)")
        for oid in links:
            if oid not in supported:
                report.error(str(obj.get("id")), f"supports unknown outcome {oid}")
            else:
                supported[oid].append(obj)
    for outcome in course.outcomes:
        oid = str(outcome.get("id"))
        _check_objective_text(oid, outcome, report)
        under = supported.get(oid, [])
        if not under:
            report.error(oid, "no module objective supports this outcome")
            continue
        top = max((RANK.get(level(o), -1) for o in under), default=-1)
        if level(outcome) in RANK and 0 <= top < RANK[level(outcome)]:
            report.warn(
                oid,
                f"outcome is at '{level(outcome)}' but its objectives only reach "
                f"'{LEVELS[top]}'; add a step that practises the outcome level",
            )


def _check_objectives(course: Course, report: Report) -> None:
    for obj in course.objectives:
        _check_objective_text(str(obj.get("id")), obj, report)
    ranked = [RANK[level(o)] for o in course.objectives if level(o) in RANK]
    if len(ranked) >= 4:
        lower = sum(1 for r in ranked if r <= RANK["understand"]) / len(ranked)
        if lower > LOWER_ORDER_MAX_SHARE:
            report.warn(
                "course",
                f"{lower:.0%} of objectives are Remember/Understand; add Apply-and-above "
                "objectives so learners can use what they learn",
            )
        if max(ranked) < RANK["analyze"]:
            report.warn("course", "no objective above Apply; consider an Analyze or Evaluate task")


def _check_alignment(course: Course, report: Report) -> None:
    objective_ids = {str(o.get("id")) for o in course.objectives}
    taught: dict[str, list[str]] = {oid: [] for oid in objective_ids}
    practised: dict[str, list[str]] = {oid: [] for oid in objective_ids}
    for bucket, target in ((course.lessons, taught), (course.activities, practised)):
        for entry in bucket:
            eid = str(entry.get("id"))
            if not refs(entry):
                report.warn(eid, "doesn't list the objectives it serves")
            for oid in refs(entry):
                if oid not in objective_ids:
                    report.error(eid, f"refers to unknown objective {oid}")
                else:
                    target[oid].append(eid)
    assessed = _assessed_by(course, report, objective_ids)
    by_id = {str(o.get("id")): o for o in course.objectives}
    for oid, obj in by_id.items():
        if not taught[oid] and not practised[oid]:
            report.error(oid, "not taught in any lesson or activity")
        if not assessed[oid]:
            report.error(oid, "not assessed by any quiz item or task")
        if RANK.get(level(obj), 0) >= RANK["apply"] and not practised[oid]:
            report.warn(oid, f"'{level(obj)}' objective has no practice activity")


def _assessed_by(course: Course, report: Report, objective_ids: set[str]) -> dict[str, list[str]]:
    by_id = {str(o.get("id")): o for o in course.objectives}
    assessed: dict[str, list[str]] = {oid: [] for oid in objective_ids}
    for item in course.items:
        iid = str(item.get("id"))
        targets = refs(item)
        if not targets:
            report.error(iid, "doesn't say which objective it assesses (`objective`)")
        for oid in targets:
            if oid not in objective_ids:
                report.error(iid, f"assesses unknown objective {oid}")
                continue
            assessed[oid].append(iid)
            item_level, obj_level = level(item), level(by_id[oid])
            if item_level not in RANK:
                report.error(iid, f"bloom {item.get('bloom')!r} is not one of {', '.join(LEVELS)}")
            elif obj_level in RANK and RANK[item_level] < RANK[obj_level]:
                report.warn(
                    iid,
                    f"assesses at '{item_level}' but {oid} is '{obj_level}'; test the level "
                    "you taught (scenario stems or a task)",
                )
            elif obj_level in RANK and RANK[item_level] > RANK[obj_level] + 1:
                report.warn(iid, f"assesses at '{item_level}', well above {oid} ('{obj_level}')")
    return assessed


def _check_items(course: Course, report: Report) -> None:
    keys: list[int] = []
    longest_is_key = 0
    single = 0
    for item in course.items:
        iid = str(item.get("id"))
        kind = item.get("type")
        if kind not in ITEM_TYPES:
            report.error(iid, f"type {kind!r} is not one of {', '.join(sorted(ITEM_TYPES))}")
            continue
        stem = str(item.get("stem", "")).strip()
        if not stem:
            report.error(iid, "missing stem")
        elif re.search(r"\b(not|except)\b", stem, re.IGNORECASE) and kind in CHOICE_TYPES:
            report.warn(iid, "negative stem (NOT/EXCEPT); rephrase, or put the word in bold")
        if kind in CHOICE_TYPES:
            key = _check_choices(iid, item, report)
            if kind == "mcq" and key is not None:
                options = [str(o) for o in item["options"]]
                keys.append(key)
                single += 1
                lengths = [len(o) for o in options]
                if lengths[key] == max(lengths) and lengths.count(max(lengths)) == 1:
                    longest_is_key += 1
        elif kind == "truefalse" and not isinstance(item.get("answer"), bool):
            report.error(iid, "truefalse answer must be true or false")
        elif kind == "short":
            answers = item.get("answer")
            if not answers or not isinstance(answers, list):
                report.error(iid, "short answer needs a list of accepted answers")
        elif kind in {"essay", "project"} and not item.get("rubric"):
            report.warn(iid, f"{kind} has no rubric; learners and graders need the criteria")
    if len(keys) >= 6:
        top = max(keys.count(k) for k in set(keys))
        if top / len(keys) > 0.5:
            report.warn("quiz", "more than half the MCQ answers are in the same position; vary it")
    if single >= 5 and longest_is_key / single > 0.6:
        report.warn("quiz", "the correct option is usually the longest one, which gives it away")


def _check_choices(iid: str, item: dict, report: Report) -> int | None:
    options = item.get("options")
    if not isinstance(options, list) or len(options) < 2:
        report.error(iid, "needs at least two options")
        return None
    texts = [str(o).strip() for o in options]
    if len(texts) == 2:
        report.warn(iid, "only two options; add distractors or use a truefalse item")
    if len({t.lower() for t in texts}) != len(texts):
        report.error(iid, "duplicate options")
    if any(re.search(r"\b(all|none) of the above\b", t, re.IGNORECASE) for t in texts):
        report.warn(iid, "avoid 'all/none of the above'; write a plausible distractor instead")
    answer = item.get("answer")
    answers = answer if isinstance(answer, list) else [answer]
    if not answers or not all(isinstance(a, int) and 0 <= a < len(texts) for a in answers):
        report.error(iid, f"answer must be option index(es) 0-{len(texts) - 1}")
        return None
    if item.get("type") == "mcq" and len(answers) != 1:
        report.error(iid, "mcq has exactly one answer; use type 'multi' for several")
        return None
    feedback = item.get("feedback")
    if not isinstance(feedback, list) or len(feedback) != len(texts):
        report.warn(iid, "add feedback for every option, explaining why it is right or wrong")
    return answers[0]


def _minutes(entry: dict, default: float = 0) -> float:
    value = entry.get("minutes", default)
    return float(value) if isinstance(value, int | float) else default


def _check_time(course: Course, report: Report) -> None:
    for lesson in course.lessons:
        lid = str(lesson.get("id"))
        if "minutes" not in lesson:
            report.warn(lid, "no minutes estimate")
        elif _minutes(lesson) > LESSON_MAX_MINUTES:
            report.warn(
                lid,
                f"{_minutes(lesson):g} min; split lessons over {LESSON_MAX_MINUTES} min "
                "into smaller chunks",
            )
    target = course.data.get("format", {}).get("total_minutes")
    total = total_minutes(course)
    if isinstance(target, int | float) and target > 0:
        if abs(total - target) / target > DURATION_TOLERANCE:
            report.warn(
                "course",
                f"planned {total:g} min vs. target {target:g} min; adjust scope or the target",
            )


def total_minutes(course: Course) -> float:
    return (
        sum(_minutes(e) for e in course.lessons)
        + sum(_minutes(e) for e in course.activities)
        + sum(_minutes(e, 1) for e in course.items)
    )


def _check_content(course: Course, report: Report, final: bool) -> None:
    gaps = 0
    for lesson in course.lessons:
        lid = str(lesson.get("id"))
        file = lesson.get("file")
        if not file:
            if final:
                report.error(lid, "no content file (`file`)")
            continue
        path = course.base / str(file)
        if not path.is_file():
            report.error(lid, f"content file {file} doesn't exist")
            continue
        gaps += len(re.findall(r"\[GAP\b", path.read_text(encoding="utf-8")))
    if gaps and final:
        report.warn("content", f"{gaps} unresolved [GAP] marker(s) in lesson files")
    elif gaps:
        report.info.append(f"{gaps} [GAP] marker(s) left in lesson files")


def _summarize(course: Course, report: Report) -> None:
    developed = sum(1 for lesson in course.lessons if lesson.get("file"))
    target = course.data.get("format", {}).get("total_minutes")
    report.info.insert(
        0,
        f"{course.data.get('title', 'Untitled')}: {len(course.modules)} modules, "
        f"{len(course.lessons)} lessons ({developed} with content), {len(course.activities)} "
        f"activities, {len(course.items)} assessment items, {total_minutes(course):g} min"
        + (f" (target {target:g})" if isinstance(target, int | float) else ""),
    )
    counts = {lv: 0 for lv in LEVELS}
    for obj in course.objectives:
        if level(obj) in counts:
            counts[level(obj)] += 1
    report.info.append(f"Bloom's levels of {len(course.objectives)} module objectives:")
    for lv, n in counts.items():
        report.info.append(f"  {lv:<11}{n:>3}  {'#' * n}")


# --------------------------------------------------------------------------- matrix


def matrix(course: Course) -> str:
    def ids(bucket: list[dict], oid: str) -> str:
        return ", ".join(str(e.get("id")) for e in bucket if oid in refs(e)) or "-"

    lines = [
        f"# Alignment matrix: {course.data.get('title', '')}",
        "",
        "| Outcome | Objective | Bloom | Taught in | Practised in | Assessed by |",
        "|---|---|---|---|---|---|",
    ]
    for obj in course.objectives:
        oid = str(obj.get("id"))
        text = str(obj.get("text", "")).replace("|", "\\|")
        lines.append(
            f"| {', '.join(refs(obj, 'supports')) or '-'} | **{oid}** {text} "
            f"| {level(obj).title()} | {ids(course.lessons, oid)} "
            f"| {ids(course.activities, oid)} | {ids(course.items, oid)} |"
        )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- export


def _gift_escape(text: object) -> str:
    return re.sub(r"([~=#{}:\\])", r"\\\1", str(text)).replace("\n", "\\n")


def _percent(n: int) -> str:
    return f"{100 / n:.5f}".rstrip("0").rstrip(".")


def export_gift(course: Course) -> str:
    out = []
    title = str(course.data.get("title", "Course")).replace("/", "-")
    groups: dict[str, list[dict]] = {}
    for item in course.items:
        groups.setdefault(course.module_of.get(str(item.get("id")), "final"), []).append(item)
    names = {str(m.get("id")): str(m.get("title", m.get("id"))) for m in course.modules}
    names["final"] = "Final assessment"
    for group, items in groups.items():
        out.append(f"$CATEGORY: $course$/top/{title}/{names.get(group, group).replace('/', '-')}")
        out.append("")
        for item in items:
            out.append(f"// {item.get('id')}: {', '.join(refs(item))} ({level(item)})")
            out.append(
                f"::{_gift_escape(item.get('id'))}::{_gift_escape(item.get('stem', ''))}"
                f"{{{_gift_answers(item)}}}"
            )
            out.append("")
    return "\n".join(out)


def _gift_answers(item: dict) -> str:
    kind = item.get("type")
    feedback = item.get("feedback")
    if kind in CHOICE_TYPES:
        options = item.get("options", [])
        answer = item.get("answer")
        keys = set(answer if isinstance(answer, list) else [answer])
        fbs = feedback if isinstance(feedback, list) else [""] * len(options)
        lines = []
        for i, option in enumerate(options):
            fb = f" #{_gift_escape(fbs[i])}" if i < len(fbs) and fbs[i] else ""
            if kind == "mcq":
                mark = "=" if i in keys else "~"
            else:
                share = (
                    _percent(len(keys)) if i in keys else f"-{_percent(len(options) - len(keys))}"
                )
                mark = f"~%{share}%"
            lines.append(f"\n  {mark}{_gift_escape(option)}{fb}")
        return "".join(lines) + "\n"
    if kind == "truefalse":
        fb = f"#{_gift_escape(feedback)}#{_gift_escape(feedback)}" if feedback else ""
        return ("TRUE" if item.get("answer") else "FALSE") + fb
    if kind == "short":
        return " ".join(f"={_gift_escape(a)}" for a in item.get("answer", []))
    return ""  # essay / project: free text, graded by rubric


def export_aiken(course: Course) -> tuple[str, int]:
    blocks, skipped = [], 0
    for item in course.items:
        options = item.get("options", [])
        if item.get("type") != "mcq" or not 2 <= len(options) <= 26:
            skipped += 1
            continue
        lines = [" ".join(str(item.get("stem", "")).split())]
        lines += [f"{chr(65 + i)}. {' '.join(str(o).split())}" for i, o in enumerate(options)]
        answer = item.get("answer")
        key = answer[0] if isinstance(answer, list) and answer else answer
        if not isinstance(key, int) or not 0 <= key < len(options):
            skipped += 1
            continue
        lines.append(f"ANSWER: {chr(65 + key)}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n", skipped


def export_csv(course: Course) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        [
            "id",
            "module",
            "objectives",
            "bloom",
            "type",
            "question",
            "options",
            "correct",
            "feedback",
        ]
    )
    for item in course.items:
        options = [str(o) for o in item.get("options", [])]
        answer = item.get("answer")
        if item.get("type") in CHOICE_TYPES:
            keys = answer if isinstance(answer, list) else [answer]
            correct = " | ".join(
                options[k] for k in keys if isinstance(k, int) and k < len(options)
            )
        elif isinstance(answer, list):
            correct = " | ".join(str(a) for a in answer)
        else:
            correct = "" if answer is None else str(answer).lower()
        feedback = item.get("feedback", "")
        writer.writerow(
            [
                item.get("id"),
                course.module_of.get(str(item.get("id")), ""),
                " ".join(refs(item)),
                level(item),
                item.get("type"),
                item.get("stem", ""),
                " | ".join(options),
                correct,
                " | ".join(map(str, feedback)) if isinstance(feedback, list) else feedback,
            ]
        )
    return buffer.getvalue()


# --------------------------------------------------------------------------- preview


def markdown_to_html(text: str) -> str:
    """Small Markdown renderer for lesson files: headings, lists, tables, quotes, code."""
    out: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(html.escape(lines[i]))
                i += 1
            out.append("<pre><code>" + "\n".join(code) + "</code></pre>")
        elif match := re.match(r"(#{1,6})\s+(.*)", stripped):
            n = len(match.group(1))
            out.append(f"<h{n}>{_inline(match.group(2))}</h{n}>")
        elif re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", stripped):
            out.append("<hr>")
        elif (
            stripped.startswith("|")
            and i + 1 < len(lines)
            and re.match(r"^\s*\|?\s*:?-{3,}", lines[i + 1])
        ):
            rows = [stripped]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            out.append(_table(rows))
            continue
        elif stripped.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            out.append(f"<blockquote>{markdown_to_html(chr(10).join(quote))}</blockquote>")
            continue
        elif re.match(r"([-*+]|\d+[.)])\s+", stripped):
            ordered = bool(re.match(r"\d", stripped))
            tag = "ol" if ordered else "ul"
            items = []
            while i < len(lines) and re.match(r"\s*([-*+]|\d+[.)])\s+", lines[i]):
                items.append(re.sub(r"^\s*([-*+]|\d+[.)])\s+", "", lines[i]))
                i += 1
                while i < len(lines) and lines[i].startswith("  ") and lines[i].strip():
                    if re.match(r"\s*([-*+]|\d+[.)])\s+", lines[i]):
                        break
                    items[-1] += " " + lines[i].strip()
                    i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{_inline(t)}</li>" for t in items) + f"</{tag}>")
            continue
        elif stripped:
            para = [stripped]
            i += 1
            while i < len(lines) and lines[i].strip() and not _starts_block(lines[i]):
                para.append(lines[i].strip())
                i += 1
            out.append(f"<p>{_inline(' '.join(para))}</p>")
            continue
        i += 1
    return "\n".join(out)


def _starts_block(line: str) -> bool:
    return bool(re.match(r"\s*(#{1,6}\s|```|>|\||[-*+]\s|\d+[.)]\s)", line))


def _inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img alt="\1" src="\2">', text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text)


def _table(rows: list[str]) -> str:
    def cells(row: str) -> list[str]:
        return [c.strip() for c in row.strip().strip("|").split("|")]

    head = "".join(f"<th>{_inline(c)}</th>" for c in cells(rows[0]))
    body = "".join(
        "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells(r)) + "</tr>" for r in rows[1:]
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def preview(course: Course) -> str:
    data = json.loads(json.dumps(course.data))
    for module in data.get("modules", []):
        for lesson in module.get("lessons", []):
            path = course.base / str(lesson.get("file", ""))
            if lesson.get("file") and path.is_file():
                text = path.read_text(encoding="utf-8")
                # The preview prints the lesson title itself, so drop the file's own H1.
                text = re.sub(r"\A\s*# [^\n]*\n", "", text)
                lesson["html"] = markdown_to_html(text)
    payload = json.dumps(data).replace("</", "<\\/")
    title = html.escape(str(data.get("title", "Course")))
    template = TEMPLATE.read_text(encoding="utf-8")
    return template.replace("__TITLE__", title).replace("__DATA__", payload)


# --------------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "matrix", "export", "preview"):
        p = sub.add_parser(name)
        p.add_argument("course", type=Path, help="path to course.json")
        if name == "check":
            p.add_argument("--final", action="store_true", help="require content; fail on warnings")
        else:
            p.add_argument("--out", type=Path, help="write to this file instead of stdout")
        if name == "export":
            p.add_argument("--format", choices=["gift", "aiken", "csv"], required=True)
    args = parser.parse_args(argv)

    try:
        course = load(args.course)
    except (OSError, ValueError) as exc:  # JSONDecodeError is a ValueError
        print(f"ERROR {args.course}: {exc}", file=sys.stderr)
        return 1

    if args.command == "check":
        report = check(course, final=args.final)
        print("\n".join(report.info))
        for line in report.errors:
            print(f"  ERROR {line}")
        for line in report.warnings:
            print(f"  WARN  {line}")
        failed = bool(report.errors) or (args.final and bool(report.warnings))
        print(f"{len(report.errors)} error(s), {len(report.warnings)} warning(s)")
        return 1 if failed else 0

    if args.command == "matrix":
        text = matrix(course)
    elif args.command == "preview":
        text = preview(course)
    elif args.format == "gift":
        text = export_gift(course)
    elif args.format == "aiken":
        text, skipped = export_aiken(course)
        if skipped:
            print(f"Aiken holds single-answer MCQ only; skipped {skipped} item(s)", file=sys.stderr)
    else:
        text = export_csv(course)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
