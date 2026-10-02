# Debugging and judging prompts

## Why this matters

Even good prompts sometimes miss. Instead of rewriting the answer yourself, find out
which part of the prompt caused the miss and fix that. Then you can judge any prompt,
yours or a colleague's, with the same checklist.

**By the end of this lesson you can** diagnose why a prompt produced an off-target answer
and judge which of two prompts better fits a task.

## Start from what you know

Each of the four parts removes a guess. So when an answer is off, ask: *which guess did
the assistant get wrong?*

## Diagnose: symptom to cause

| Symptom in the answer | Most likely missing part |
|---|---|
| Right topic, wrong purpose (a reminder instead of a complaint) | Context: the goal |
| Wrong depth or jargon level | Context: the audience |
| Too long, wrong layout | Format |
| Right content, wrong tone or style | Examples |
| Did something else entirely | Task: unclear verb, or several tasks at once |

## The prompt checklist

Use it to judge a prompt before you send it, or to compare two:

1. Is there exactly one clear task verb?
2. Does it say who the answer is for and why?
3. Does it state the length and shape?
4. Is there an example, or a good reason not to have one?
5. Would a new colleague understand it with no other information?

The better prompt is the one that passes more checks **for this task**. A quick lookup
doesn't need an example, so don't mark it down for missing one.

## Worked example

> **Prompt A:** "Write a detailed, comprehensive, professional summary."
> **Prompt B:** "Summarize these meeting notes for people who missed it: decisions first,
> then actions with owners, under 120 words."

A fails checks 2 and 3: "detailed" and "comprehensive" sound helpful but say nothing
about the reader or the length. B passes 1-3 and 5. **B is better**, and you can now say
exactly why.

## Try it

An assistant wrote a 900-word answer when you wanted a quick reply to a colleague's
question. Diagnose it. *Missing format: no length or shape was given. Add "two or three
sentences".*

## Key takeaways

- Match the symptom to the missing part instead of rewriting the answer by hand.
- Judge prompts with the five-point checklist, relative to the task.
- Vague adjectives ("detailed", "professional") don't replace context or format.

*Source: S1, "Troubleshooting".*
