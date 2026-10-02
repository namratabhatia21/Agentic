# The anatomy of a prompt

## Why this matters

You asked an assistant for help and got something generic, so you rewrote it yourself.
Most of the time the assistant wasn't the problem. It was missing information that only
you had. In this lesson you'll learn the four parts that carry that information.

**By the end of this lesson you can** identify the four parts of an effective prompt.

## Start from what you know

Think of the last time you briefed a new colleague. You probably told them what to do,
why, what the result should look like, and maybe showed them a past example. A prompt
needs the same four things.

## The four parts

| Part | Question it answers | Example |
|---|---|---|
| **Task** | What should the assistant do? | "Summarize this report" |
| **Context** | Who is it for, and why? | "for our CFO, who cares about cost overruns" |
| **Format** | What should the answer look like? | "in 5 bullet points, under 100 words" |
| **Examples** | What does good look like? | "Here is last quarter's summary: ..." |

You won't need all four every time. A quick fact question needs only a task. The longer
or more important the answer, the more the other three pay off.

## Worked example

> **Before:** Summarize this report.
>
> **After:** Summarize this report for our CFO, who cares about cost overruns. Use 5 bullet
> points, under 100 words, and lead with the biggest risk. Here is last quarter's summary
> as a model: [paste]

The "after" prompt is four sentences longer, and every sentence removes a guess.

## Try it

Label each part of this prompt: *"Draft a welcome email for new hires starting Monday.
Keep it under 150 words and friendly. They work remotely and will get a laptop by
courier."*

- Task: draft a welcome email
- Context: new hires starting Monday, remote, laptop by courier
- Format: under 150 words, friendly
- Examples: none. Adding last year's email would make the tone match even better.

## Key takeaways

- An effective prompt answers four questions: task, context, format, examples.
- Each part replaces a guess the assistant would otherwise make.
- Add parts in proportion to how much the answer matters.

*Source: S1, "Prompt structure".*
