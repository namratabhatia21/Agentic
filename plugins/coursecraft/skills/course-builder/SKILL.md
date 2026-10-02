---
name: course-builder
description: Turn any source content (documents, PDFs, slides, transcripts, web pages, notes or just a topic) into a complete online course using the ADDIE model and Bloom's revised taxonomy. Produces a learner analysis, measurable learning objectives, an aligned module and lesson plan, lessons structured on Gagné's nine events, practice activities, quizzes with answer feedback, rubrics, LMS-ready quiz exports (Moodle GIFT, Aiken, CSV), a clickable HTML preview and a Kirkpatrick evaluation plan. Use when someone wants to create, design, outline, convert or improve a course, training, workshop, curriculum, e-learning module, lesson plan, quiz or learning objectives, or mentions instructional design, ADDIE, SAM, Bloom's taxonomy, backward design or course alignment.
license: MIT
---

# Course builder

Build an online course the way an instructional designer would. ADDIE is the process,
Bloom's taxonomy sets the level of every objective, and backward design keeps every
lesson, activity and question aligned to an outcome. Everything comes from the user's
source content.

The blueprint is one file, `course/course.json`, and lessons are Markdown files next to
it. A script checks the alignment and builds the exports, so quality is measured rather
than guessed:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/course_tool.py" check course/course.json
```

`${CLAUDE_SKILL_DIR}` is this skill's folder. Outside Claude Code, use the path of the
folder that contains this file. Subcommands: `check [--final]`, `matrix`,
`export --format gift|aiken|csv`, `preview`. Each one prints its result or writes to
`--out FILE`.

## 0. Scope the request

Match the user's request:

| They ask for | Do |
|---|---|
| A full course from content | All five phases below |
| An outline / curriculum | Analysis + Design, then stop and offer Development |
| Objectives only | Write them with [references/blooms.md](references/blooms.md); still run `check` on a minimal blueprint |
| A quiz from content | Objectives first (you can't align questions without them), then items and an export |
| A single lesson or workshop | The compressed variant in [references/addie.md](references/addie.md) |
| Improve an existing course | Rebuild its blueprint, run `check` and `matrix`, then fix the weak spots |
| Fast iteration, unclear needs | SAM: design everything, develop one module fully, review, then continue |

Read the source content first: files, URLs, pasted text. For long sources, read in
sections and build the source map as you go. Then ask the user **once**, in one message,
only for what you can't infer: who the learners are and what they already know, the goal,
total length, self-paced or live, and the platform/LMS. Offer sensible defaults so they
can just say "go": adult professionals, 60-90 minutes, self-paced, Markdown + Moodle
GIFT.

## 1. Analysis

Follow the Analysis section of [references/addie.md](references/addie.md) and write
`course/01-analysis.md`: persona, gap, goal, constraints, and the **source map**. The
source map gives each source an ID (S1, S2...) and lists its topics with page, section or
timestamp. List what the goal needs but the sources don't cover as `[GAP]` items.

## 2. Design

Read [references/blooms.md](references/blooms.md), then build `course/course.json` to
the format in [references/course-json.md](references/course-json.md):

1. Write 2-6 course outcomes, mostly at Apply or above, each with one observable verb.
2. Decide the evidence for each outcome (final project, exam), then the formative checks.
3. Map modules from simple to complex and write 2-5 objectives per module, each linked to an
   outcome with a Bloom level and knowledge type.
4. Plan lessons of 5-15 minutes, with a practice activity for every Apply+ objective, and
   time estimates that add up to the target.
5. Run `check` and fix every ERROR. Treat WARNs as design feedback and fix them unless
   there is a reason not to.
6. Write `course/02-design.md`: persona summary, module map with timings, assessment
   strategy, and the alignment matrix from `course_tool.py matrix`.

**Checkpoint**: show the user the outcomes, the module map and the total time, and get a
yes before Development. It's the most expensive phase, and changing the outline afterwards
means rewriting it. Skip the checkpoint only if the user told you not to stop.

## 3. Development

Start only once `01-analysis.md` exists and `course.json` passes `check`. Lessons written
before the blueprint drift from the objectives. Follow
[references/lesson-design.md](references/lesson-design.md) and
[references/assessment.md](references/assessment.md):

- Write one Markdown file per lesson in `course/modules/`, using the Gagné lesson template.
  Set the lesson's `file` in `course.json` when it's done.
- Write every activity's `instructions`, then the quiz items in `course.json`, with
  feedback for every option and rubrics for tasks. Each item tests its objective's level:
  use scenarios for Apply and Analyze, and tasks for Evaluate and Create.
- Add what the course needs: a glossary, a one-page job aid, video scripts (two-column),
  and a facilitator guide for live delivery.
- For courses of more than about 6 lessons, develop module by module and run `check` after
  each one.

## 4. Implementation

- Export the quizzes in the platform's format:
  `export --format gift --out course/assessments/quiz.gift`, plus `aiken` or `csv` as
  needed.
- Build `course/preview.html` with `preview` so the user and pilot learners can click
  through the course and take the quizzes.
- Write `course/04-implementation.md`: platform setup steps, quiz settings, completion
  rules, a pilot plan with 3-5 target learners, and a launch checklist that includes
  accessibility.

## 5. Evaluation

Write `course/05-evaluation.md`: Kirkpatrick levels 1-4 with ready-to-use instruments
(survey, pre/post test from the item bank, follow-up questions, the business metric from
Analysis), the item-analysis plan, and revision triggers.

Finish with `check --final`. It must pass with 0 errors and 0 warnings, or you must name
each remaining warning and say why it stays.

## Hand-off

Reply with:
- the outcomes, the module map with minutes, and the Bloom distribution from `check`
- the files you created
- any `[GAP]`s the user needs to fill
- how to open the preview and import the quiz

Keep it short; the files hold the detail.

## Rules

- **Stay faithful to the source.** Every factual claim in a lesson comes from the source
  map, cited as `*Source: S1, p. 4*`. When the source is silent, write `[GAP: ...]`
  and tell the user. Never invent facts, statistics, quotes or references.
- **Respect copyright.** Teach the ideas in new words with new examples. Quote briefly and
  with attribution. Don't paste long passages from the source into lessons.
- **Use observable verbs only.** No objective or outcome starts with understand, know,
  learn, appreciate or be aware of. The checker rejects them.
- **Align everything.** Every objective is taught, practised (if Apply or above) and
  assessed at its own level. Every item and activity maps to an objective. Cut content
  that serves no objective, however interesting.
- **Write for the learner.** Use plain language, "you", short paragraphs, realistic and
  inclusive examples, and accessible media (alt text, captions, heading structure).
- **Run the script, don't eyeball.** Run `check` after every change to `course.json`, and
  report its numbers instead of claiming quality.
