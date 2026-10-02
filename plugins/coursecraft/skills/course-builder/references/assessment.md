# Assessment

## Strategy

- **Formative** (each module): low stakes, instant feedback, retry allowed. Its job is
  practice and showing learners where they are. 2-5 items per module objective set.
- **Summative** (end of course): shows the course outcomes were met. For Apply-and-above
  outcomes, use a task or project with a rubric, not only MCQ.
- **Mastery**: set the pass mark from the stakes, typically 70-80% for formative
  readiness and 80%+ for compliance or certification. Say what happens on a fail (review
  lessons X and Y, then retry).
- Every item maps to exactly one objective (two at most for projects), at the
  objective's Bloom level. `course_tool.py check` enforces this.

## Writing choice items (MCQ)

Stem:
- Make it a complete question or problem that makes sense without the options. Test: can
  a strong learner answer it with the options covered?
- Put the shared words in the stem, not repeated in every option.
- Phrase it positively. If NOT or EXCEPT is unavoidable, put it in **bold**.
- For Apply and Analyze, open with a short realistic scenario.

Options:
- Use 3-4 options. A third distractor nobody picks adds reading time, not rigour.
- Build distractors from **real misconceptions** and common errors, so each wrong answer
  tells you what the learner misunderstood.
- Keep options similar in length, grammar and detail. The correct one is often the
  longest; the checker warns when it usually is.
- Avoid "all of the above", "none of the above", "both A and C", and absolute words
  (always, never) that give the answer away.
- Vary the position of the correct answer. The checker warns when more than half share
  one position.
- Write **feedback for every option**: why the right one is right, and what misconception
  each wrong one shows.

Other types:
- **True/false**: only for clear-cut statements, and only at Remember or Understand. Avoid
  trick wording.
- **Multiple response** (`multi`): say "Select all that apply" in the stem. Each option must
  be clearly right or wrong on its own.
- **Short answer**: list every acceptable answer (spelling variants, synonyms).
- **Essay / project**: always with a rubric, a word or time guide, and what to submit.

## Rubrics

Analytic rubrics: 3-5 criteria, each tied to an objective, with 3-4 performance levels
described in observable terms:

| Criterion | Excellent (4) | Proficient (3) | Developing (2) | Beginning (1) |
|---|---|---|---|---|
| <Criterion tied to M2.3> | <what you'd see> | ... | ... | ... |

In `course.json`, the short form is a list of `{criterion, excellent}` pairs. Put the full
table in the course materials.

## Evaluation instruments (Kirkpatrick)

**Level 1: end-of-course survey** (5-point agree scale unless noted):
1. The course was relevant to my work.
2. I can use what I learned in the next two weeks.
3. The examples and activities helped me learn.
4. The length was right for the content. (too short / about right / too long)
5. What will you do differently after this course? (open)
6. What one change would most improve the course? (open)

**Level 2: pre/post test**: 8-12 items from the item bank covering every outcome. Give
the same form before and after, or two parallel forms.

**Level 3: follow-up** at 30-60 days:
1. How often have you used <skill> since the course? (never / once / weekly / daily)
2. Describe one time you used it. What happened?
3. What got in the way of using it?
Add a manager or artefact check where possible (a sample of real work).

**Level 4**: the metric named in Analysis, measured before and after, with a note on
other factors that could explain a change.

## Item analysis (after the first cohort)

For each item:
- **Difficulty** (p) = share of learners who got it right. As a rule of thumb, look again
  at items above 0.9 (too easy, or the answer is guessable) and below 0.3 (unclear wording,
  wrong key, or the lesson didn't teach it).
- **Discrimination** = how much better high scorers do on the item than low scorers. As a
  rule of thumb, revise items with discrimination below 0.2, and check any negative
  values for a wrong key first.
- **Distractors**: a distractor nobody picks isn't working. Replace it with a real
  misconception.
