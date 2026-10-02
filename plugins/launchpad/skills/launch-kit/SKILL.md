---
name: launch-kit
description: Get a Claude Code skill, plugin or small open-source repo ready to launch, then write its marketing kit - a preflight check of the skill files, a README that turns visitors into installs, a 30-second screen-recording script for Reels, TikTok and Shorts, and ready-to-post copy for X, LinkedIn, Reddit, Hacker News and awesome-lists. Use when someone wants to publish, launch, promote, market, share or grow a skill, plugin or GitHub project, or asks why theirs gets no installs or stars.
license: MIT
---

# Launch kit

Turn a working skill (or plugin, or repo) into something people find, understand in
five seconds, and install with one command.

## 1. Understand what is being launched

Read the target's `SKILL.md` files, `README.md`, and any `.claude-plugin/plugin.json` or
`.claude-plugin/marketplace.json`. With no path given, use the current directory. Work out:

- **Promise**: one outcome-first sentence, 12 words or fewer. "Turns a Figma link into a
  working landing page", not "A skill for frontend work".
- **Audience**: who hits this problem every week, and where they hang out online.
- **Before / after**: what Claude does without the skill versus with it. This contrast is
  the whole pitch, so make it concrete.
- **Proof**: one prompt whose result can be screen-recorded in under 30 seconds.

Ask the user only for what the files can't tell you: the public repo URL, and which
channels they actually post on. Ask both in one message.

## 2. Preflight

Run the checker on the target:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/preflight.py" <path>
```

`${CLAUDE_SKILL_DIR}` is this skill's folder. Outside Claude Code, use the path of the
folder that contains this file.

Fix every ERROR before writing any marketing: a launch that sends people to a broken
install wastes the one spike of attention it gets. Fix WARNs too unless the user decides
otherwise, then re-run the checker until it reports 0 errors. If the `claude` CLI is
installed, also run
`claude plugin validate <plugin-or-marketplace-dir>`. It is the authority on plugin
manifests.

Then read the skill's `description` yourself. It decides whether the skill ever runs:

- It opens with what the skill does, in words a user would actually type.
- It names the situations that should trigger it ("Use when ...").
- It uses concrete nouns: file types, frameworks, tools, platforms.

Write three prompts that should trigger the skill and two near-misses that shouldn't.
Put them in the kit's checklist so the user can test triggering before launch.

## 3. Write the kit

Read [references/channels.md](references/channels.md) first, then create a `launch/`
folder in the target repo. Never overwrite an existing file there without asking.

| File | Contents |
|---|---|
| `launch/README-draft.md` | Full README in the structure from the reference. Edit `README.md` directly only if the user asked for that |
| `launch/demo-script.md` | Shot list for a 9:16 vertical video (20-40 s) and a 16:9 cut, plus the README GIF |
| `launch/posts.md` | Copy for each channel the user uses, each written natively for that channel |
| `launch/checklist.md` | Dated launch plan, trigger test prompts, and directory submissions |

The install section must list every route that really works for this repo. Check names
and paths against the files; never guess them:

- Plugin marketplace, if `.claude-plugin/marketplace.json` exists:
  `claude plugin marketplace add <owner>/<repo>` then
  `claude plugin install <plugin>@<marketplace>`
- Skills CLI: `npx skills add <owner>/<repo>`
- Manual: copy the skill folder to `~/.claude/skills/<skill-name>/`

## 4. Hand off

Reply with the promise line, the preflight result, the files you wrote, and the three
highest-leverage next actions. These are usually: record the demo, post on the one or two
channels where the audience already is, then submit to directories.

## Rules

- Make only honest claims. Every number, benchmark, or "works with X" must be something
  you verified or the user told you. Never invent testimonials, star counts or user numbers.
- Don't suggest growth tactics that break platform rules: no bought stars or followers, no
  vote rings, and no pasting the same post into many subreddits. Tell the user to disclose
  that they're the author on Reddit and Hacker News.
- Write like a person: specific and plain. Don't use words like "revolutionize",
  "game-changer" or "unlock". Use at most one emoji per post and no more than three
  hashtags.
- Write each channel's copy natively for that channel. Don't paste one text everywhere.
