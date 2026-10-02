# CourseCraft

Turn any content into a complete online course, designed the way an instructional
designer would do it.

CourseCraft is a Claude Code plugin with one skill, `course-builder`. Give it a PDF, a
slide deck, a video transcript, a web page, your notes, or just a topic. It walks through
**ADDIE** (Analysis, Design, Development, Implementation, Evaluation), writes every
objective at a deliberate **Bloom's taxonomy** level, and keeps lessons, activities and
quiz questions aligned to those objectives.

## What you get

```
course/
├── 01-analysis.md          learner persona, gap, goal, source map, [GAP]s
├── course.json             the blueprint: outcomes, modules, objectives, lessons, items
├── 02-design.md            module map, timings, assessment strategy, alignment matrix
├── modules/*.md            lessons on Gagné's nine events, with source citations
├── assessments/quiz.gift   Moodle import (also Aiken and CSV)
├── preview.html            click through the course and take the quizzes, offline
├── 04-implementation.md    LMS setup, pilot plan, launch and accessibility checklist
└── 05-evaluation.md        Kirkpatrick levels 1-4: survey, pre/post test, follow-up
```

The checker does what a reviewer would. It catches:
- objectives that can't be measured ("understand...")
- verbs that don't match their Bloom level
- objectives that are never taught, practised or assessed
- quiz items pitched below their objective
- lessons that are too long
- answer keys that give themselves away

## Install

```bash
claude plugin marketplace add namratabhatia21/Agentic
claude plugin install coursecraft@namrata-skills
```

With the cross-agent skills CLI: `npx skills add namratabhatia21/Agentic`. Or copy
`skills/course-builder/` to `~/.claude/skills/course-builder/`.

## Use it

```text
/coursecraft:course-builder ./handbook.pdf
```

Or just ask:
- "Turn these meeting transcripts into a 60-minute onboarding course for new support agents."
- "Make a Moodle quiz from chapter 3, with objectives at Apply level."
- "Here's my workshop outline. Check the alignment and fix the objectives."

Claude asks a few questions in one go (audience, goal, length, platform), shows you the
outline for approval, then writes the course.

The script also runs on its own (Python 3.11+, no dependencies):

```bash
T=skills/course-builder/scripts/course_tool.py
python3 $T check   course/course.json            # Bloom + alignment QA
python3 $T matrix  course/course.json            # alignment matrix (Markdown)
python3 $T export  course/course.json --format gift --out quiz.gift
python3 $T preview course/course.json --out preview.html
```

Try it on the bundled example, a 90-minute course on writing better prompts:

```bash
python3 $T check skills/course-builder/assets/example-course/course.json --final
python3 $T preview skills/course-builder/assets/example-course/course.json --out preview.html
```

## Frameworks used

| Framework | Where |
|---|---|
| ADDIE (and SAM for fast iteration) | The overall process and the files it produces |
| Bloom's revised taxonomy + knowledge dimension | Every outcome, objective and quiz item |
| Backward design | Outcomes, then evidence, then lessons |
| ABCD objectives | How objectives are written |
| Gagné's nine events, Merrill's First Principles | Lesson structure |
| Mayer's multimedia principles, cognitive load | Lesson and media design |
| UDL and WCAG basics | Accessibility checklist |
| Kirkpatrick's four levels, item analysis | Evaluation plan |

## License

MIT
