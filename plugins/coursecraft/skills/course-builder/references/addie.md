# ADDIE, phase by phase

ADDIE is the backbone: **A**nalysis, **D**esign, **D**evelopment, **I**mplementation,
**E**valuation. Each phase ends with a file in `course/` and a "done when" test. Do the
phases in order, but go back when a later phase shows a gap (a quiz you can't write often
means a weak objective).

Inside Design, use **backward design** (Wiggins & McTighe): outcomes first, then the
evidence that shows them (assessments), then the learning activities. Never the reverse.

## A: Analysis → `01-analysis.md`

Answer these, from the source material and the user's brief:

| Question | Write down |
|---|---|
| Who are the learners? | A persona: role, prior knowledge, motivation, constraints (time, device, language, accessibility needs) |
| What's the gap? | What they can't do today that they need to do. A gap in knowledge, skill, or motivation? Training only fixes the first two |
| What's the goal? | The business or personal result, and how you'd see it ("fewer support tickets", "passes the exam") |
| What does the source cover? | A **source map**: each source gets an ID (S1, S2...), then a list of its main topics with location (page, timestamp, section) |
| What's missing? | Topics the goal needs that the sources don't cover. Mark each as a `[GAP]` to fill from the user or leave out |
| Constraints? | Total time, delivery (self-paced / live / blended), platform or LMS, deadline, budget for media |

Done when: the persona, gap, goal, source map and constraints are written, and the user
has confirmed anything you inferred.

## D: Design → `course.json` + `02-design.md`

1. **Outcomes**: 2-6 course outcomes in Bloom terms (see [blooms.md](blooms.md)).
2. **Assessment strategy**: for each outcome, decide the evidence: final project, exam,
   or portfolio. Then decide formative checks per module.
3. **Module map**: group content into modules of roughly equal weight. Sequence them simple
   to complex, known to unknown, and prerequisites first.
4. **Objectives**: 2-5 per module, each linked to an outcome (`supports`), with a Bloom
   level and knowledge type.
5. **Lessons and activities**: lessons of 5-15 minutes, each serving 1-2 objectives. At
   least one practice activity for every objective at Apply or above.
6. **Timing**: minutes per lesson, activity and assessment, summed against the target.
7. Write the blueprint in `course.json` ([course-json.md](course-json.md)) and run
   `course_tool.py check`. Then generate the alignment matrix with `course_tool.py
   matrix` and put it in `02-design.md`, with the persona summary, module map and
   assessment strategy.

Done when: `check` reports 0 errors, every objective is taught, practised (if Apply+) and
assessed, and the user has approved the outline.

## D: Development → `modules/*.md`, items in `course.json`

- Write each lesson with the template in [lesson-design.md](lesson-design.md).
- Write the activities' instructions, and the quiz items and rubrics using
  [assessment.md](assessment.md).
- Add supporting material where it helps: glossary, job aid / cheat sheet, video scripts,
  slide outlines, a facilitator guide for live sessions.
- **Ground every claim** in the source map and cite it (`*Source: S2, p. 14*`). Where the
  source is silent, write `[GAP: what's missing]` instead of inventing facts.
- Set `file` on each lesson in `course.json` as you finish it.

Done when: `check --final` passes, no `[GAP]` markers remain (or the user accepted them),
and lessons read well aloud.

## I: Implementation → `04-implementation.md` + exports

- Export quizzes for the platform: `course_tool.py export --format gift` (Moodle),
  `aiken` (Moodle and other LMSs, single-answer MCQ only), or `csv` (spreadsheets, most
  course platforms' bulk import, or manual entry).
- Build `preview.html` with `course_tool.py preview` for review and pilot learners.
- Write the setup steps for the chosen platform. Include course settings, completion
  rules, quiz settings (attempts, pass mark, feedback timing), and a release schedule for
  cohorts.
- Write a **pilot plan**: 3-5 people from the target audience, what they do, what you ask
  them afterwards.
- Write a launch checklist: links work, media has captions, quizzes import cleanly,
  accessibility check done, support contact given.

Done when: exports import cleanly (or the user has the steps to do it), and the pilot is
scheduled.

## E: Evaluation → `05-evaluation.md`

Plan evaluation at Kirkpatrick's four levels, with the instruments ready to use:

| Level | Question | Instrument |
|---|---|---|
| 1 Reaction | Did they find it relevant and engaging? | 5-8 question end-of-course survey, mostly about relevance and confidence |
| 2 Learning | Did they learn it? | Pre/post test built from the item bank; item analysis after the first cohort |
| 3 Behavior | Do they use it at work? | 30-60 day follow-up: self-report plus a manager or artefact check |
| 4 Results | Did the goal from Analysis move? | The metric named in Analysis, before vs. after |

Also list the **revision triggers**: an item most people get wrong, a lesson with a big
drop-off, a survey theme. Add the cadence for reviewing them.

Done when: the instruments are written and tied to the goal from Analysis.

## Variants

- **SAM (Successive Approximation Model)**: for tight deadlines or unclear needs. Do a
  short Analysis, design the whole course but develop **one module fully** as a prototype,
  review it with the user or pilot learners, then iterate and roll the pattern out.
- **Single lesson or workshop**: compress ADDIE into one `lesson-plan.md`: persona and
  goal, 1-3 objectives, a Gagné-structured plan with timings, one check, one reflection.
- **Improve an existing course**: start with Evaluation. Run `check` on a blueprint of
  the existing course and read the alignment matrix. Then work back through Design and
  Development on the weak spots.
