# Creating and launching a Claude Code skill

How to build a skill like the ones going round on Instagram and GitHub (Anthropic's
`frontend-design`, the Remotion video skills, the Watermelon UI component skill), package
it so anyone can install it with one command, and market it so people actually use it.

There is a working example in this repo: [`plugins/launchpad`](../plugins/launchpad), a
plugin whose `launch-kit` skill checks a skill and writes its launch material. Section 6
shows how to use it.

## 1. What a skill is

A skill is a folder with a `SKILL.md` file in it. The file has instructions for Claude,
plus a short YAML header that says what the skill is for:

```
my-skill/
├── SKILL.md            required: frontmatter + instructions
├── references/         optional: long docs Claude reads only when needed
├── scripts/            optional: code Claude runs (deterministic steps, validators)
└── assets/             optional: templates, images, fonts
```

```markdown
---
name: my-skill
description: What it does, then when to use it. Use when the user asks for ...
---

# My skill

Step-by-step instructions Claude follows whenever the skill is active.
```

Skills load in stages, which is why they're cheap to install and why the description
matters so much:

| Stage | What's in context | Cost |
|---|---|---|
| Always | `name` + `description` of every installed skill | ~100-200 tokens each |
| When triggered | The `SKILL.md` body (Claude decides from the description, or you type `/my-skill`) | Size of the file |
| When needed | Files in `references/`, output of `scripts/` | Only what's read or run |

A skill is the right tool when you want Claude to *know how* to do something. The other
options:

| Use | When |
|---|---|
| `CLAUDE.md` | Facts and rules for one project, always loaded |
| **Skill** | A reusable procedure or expertise, loaded only when relevant |
| MCP server | Claude needs live access to an outside system (an API, a database, a component registry) |
| Plugin | A bundle (skills, agents, hooks, MCP servers) that people install and update as one unit |

The popular "skills" often combine these. Watermelon UI, for example, ships a skill that
teaches Claude when and how to use the library, plus an MCP server that searches and
installs the components.

## 2. Pick an idea that can spread

Popular skills share a few traits:

- **They fix something visibly weak in Claude's default output.** `frontend-design` exists
  because default AI UIs look generic. The before/after is obvious in one screenshot.
- **They teach Claude a tool it doesn't know well enough.** Remotion skills turn "make a
  video" into React compositions that render. Watermelon UI makes Claude install real,
  polished components instead of hand-writing mediocre ones.
- **They package an expert workflow people repeat.** Examples: plan → test → implement
  (Superpowers), a review checklist, an SEO audit.
- **The result is visual or shareable.** A video, a web page or a design spreads on
  Instagram and TikTok. A better commit message doesn't, however useful it is.

Check an idea against these questions before building it:

1. Can you show the before/after in a 30-second screen recording?
2. Do the people with this problem hit it every week?
3. Does something already do it? Search [skills.sh](https://skills.sh) and GitHub
   (`awesome claude skills`). If it does, narrow the idea (a specific framework, industry
   or output format) rather than build the same thing again.

Ideas that match this repo's strengths (agents, Hugging Face, cloud):
- **`hf-model-scout`**: picks the right open model for a task, checking license, size,
  tool-calling support and current benchmarks on the Hub.
- **`cloud-cost-check`**: reads a `docker-compose.yml` or Terraform plan and estimates the
  monthly cost on GCP, AWS and Azure, flagging what free credits cover.
- **`agent-tool-maker`**: turns any REST API docs page into a tested tool for an agent
  framework.

## 3. Build it

### Step 1: start as a personal skill

Iterate locally before you think about packaging. Personal skills load in every project:

```bash
mkdir -p ~/.claude/skills/my-skill
$EDITOR ~/.claude/skills/my-skill/SKILL.md
```

Use `.claude/skills/my-skill/` instead to share it with one repo's collaborators. Anthropic's
`skill-creator` skill can interview you and write the first draft. Ask Claude to "create a
skill for X".

### Step 2: write the frontmatter

```yaml
---
name: commit-poet
description: Writes git commit messages from the staged diff, with a short imperative
  subject and a why-focused body in the repo's existing style. Use when the user asks
  for a commit message, says "commit this", or wants to tidy commit history.
license: MIT
---
```

- **`name`**: kebab-case, at most 64 characters, the same as the folder name. It becomes
  the `/command`.
- **`description`**: decides whether the skill ever runs. Start with what it does, using
  the words people actually type. Then say when to use it ("Use when ..."). Name concrete
  things: file types, frameworks, platforms. Keep it under 1,024 characters (the open
  Agent Skills limit). Claude Code allows 1,536 for `description` + `when_to_use`.
  - Bad: `A skill for git.`
  - Good: the example above.
- **Stay portable.** `name`, `description`, `license`, `compatibility`, `metadata` and
  `allowed-tools` work everywhere: Claude Code, claude.ai, the Skills API, and other agents
  that follow the [Agent Skills](https://agentskills.io) standard (Codex, Cursor, Gemini
  CLI and others). Claude Code also understands `disable-model-invocation`,
  `argument-hint`, `context: fork`, `model`, `hooks`, `paths` and more, but uploads to
  claude.ai reject them. Use them only if Claude Code is your only target.

### Step 3: write the instructions

- Write them as **standing instructions** for the whole task, in the imperative: "Read
  X. Run Y. Never Z." Claude doesn't re-read the file on later turns.
- Use numbered steps for the workflow, then a short **Rules** section for the
  non-negotiables.
- Show one good example of the output. Examples steer Claude more than adjectives do.
- Keep `SKILL.md` under 500 lines. Move long material to `references/*.md` and link it
  ("Read [references/api.md](references/api.md) before calling the API").
- Put anything that must be exact (validation, file conversion, API calls) in
  `scripts/` and tell Claude to run it: `python3 "${CLAUDE_SKILL_DIR}/scripts/check.py"`.
  Code is cheaper and more reliable than asking Claude to do it by hand every time.

### Step 4: test it

1. **Direct use**: type `/my-skill` and check the result.
2. **Triggering**: in a fresh session, ask in plain words, without naming the skill. Write
   three prompts that *should* trigger it and two near-misses that *shouldn't*. If it
   misfires, fix the description, not the body.
3. **On real tasks**: run it on three or four real inputs, including a messy one.
   Compare with and without the skill. If you can't see a difference, neither will users.
4. **Measure**: `skill-creator` can run evals that compare with and without the skill. For
   plugins, `claude plugin eval` does the same in CI. `/skill-doctor` shows what each
   skill costs in context.

## 4. Package it so anyone can install it

| Route | People install with | Updates | Best for |
|---|---|---|---|
| Repo with a `skills/` folder | `npx skills add owner/repo` ([skills CLI](https://skills.sh), works across ~20 agents) | Re-run the command | Widest reach, any agent |
| Plugin + marketplace in the repo | `claude plugin marketplace add owner/repo` then `claude plugin install name@marketplace` | `claude plugin update`, or auto-update | Claude Code users, versioned releases, bundling hooks and MCP servers |
| Anthropic's directory | Browsing on claude.ai, in Cowork and in Claude Code | Automatic after review | Mainstream reach. Submit at [claude.ai/directory/manage](https://claude.ai/directory/manage) (paid plan, reviewed) |

You don't have to choose: one repo can serve the first two routes, and later the third.
For anything you want to be popular, give it **its own repo** (stars, issues and the README
all point at one thing):

```
commit-poet/                         ← github.com/you/commit-poet
├── .claude-plugin/
│   ├── plugin.json                  { "name": "commit-poet", "version": "1.0.0", ... }
│   └── marketplace.json             one entry with "source": "./"
├── skills/commit-poet/
│   ├── SKILL.md
│   └── references/style.md
├── README.md                        promise line, GIF, install commands
└── LICENSE
```

```json
// .claude-plugin/marketplace.json
{
  "name": "commit-poet",
  "owner": { "name": "Your Name" },
  "plugins": [{ "name": "commit-poet", "source": "./" }]
}
```

Before every release:

```bash
claude plugin validate . --strict          # manifests and frontmatter
claude plugin marketplace add ./           # install it the way users will...
claude plugin install commit-poet@commit-poet
claude plugin details commit-poet          # ...and check the skill shows up
```

Choose the plugin `name` once and never rename it, because installs are recorded by name.
Either bump `version` on every release, or leave it out so the git commit is used. If you
set it and forget to bump it, users never get the update.

## 5. Market it

Every install goes through the same funnel. Each step loses most people, so fix them in
order:

```
SEE IT ──► GET IT ──► INSTALL IT ──► IT WORKS FIRST TIME ──► SHARE IT
 video      README      one command    good description        shareable output
            promise     that works     and instructions        "made with X"
```

**Repo page (get it).** The first screen needs a one-line promise, a demo GIF, and the
install commands. Add GitHub topics (`claude-code`, `claude-skills`, `agent-skills`,
`claude-code-plugin` plus your domain), a 1280x640 social preview image, and a `v1.0.0`
release. Pin the repo on your profile.

**Demo video (see it).** This is how the skills you saw on Instagram spread. Make a
20-40 second vertical video: show the finished result in the first two seconds,
optionally the generic result without the skill, then the prompt and Claude working at
4-8x speed, then the result again and the repo name. Burn in captions and show real
output, never a mock-up. Post the same story as a 16:9 cut on X, LinkedIn and YouTube, and
use the middle part as the README GIF.

**Channels.** Each one needs copy written for it. Don't paste the same text everywhere:

| Channel | What works |
|---|---|
| Instagram Reels / TikTok / Shorts | The vertical demo. Hook in two seconds, CTA "link in bio", pinned comment with the repo name |
| X | A 4-5 post thread with the video first. Many put the repo link in a reply |
| LinkedIn | A first-person story (problem, what you built, what you learned) with native video |
| Reddit | r/ClaudeAI, r/ClaudeCode, plus one subreddit for your domain. Read each sub's self-promotion rules, say you're the author, and reply to every comment |
| Hacker News | `Show HN:` only if it's technically interesting. Post a first comment with the backstory |
| Awesome lists | One-line PRs to active `awesome-claude-skills`-style lists |
| skills.sh | Ranked by installs through `npx skills add`, so put that command in the README |
| Anthropic's directory | Submit once the plugin is stable: [claude.ai/directory/manage](https://claude.ai/directory/manage) |

**Launch plan.**
- **Week before**: preflight passes, a fresh install works on another machine, README and
  GIF are done, videos are recorded.
- **Launch day**: post the video, the X thread, LinkedIn and one subreddit, then spend two
  to three hours replying to everything.
- **First week**: a second subreddit or Show HN only if day one worked. Send the
  awesome-list PRs and the directory submission.
- **After that**: ship a v1.1 with something users asked for and announce it. Make one
  short video per new use case. Each one is another chance to be seen.

**Measure.** GitHub **Insights → Traffic** shows which sites send visitors and stars.
skills.sh shows installs. Double down on the one channel that works.

**Don't**: buy stars or followers, run vote rings, post the same text to many
subreddits, or claim numbers you haven't measured. Platforms and communities spot it, and
one bad thread can sink a launch.

## 6. Use the example in this repo

`launchpad` packages sections 3-5 as a skill. Install it from this repo's marketplace:

```bash
claude plugin marketplace add namratabhatia21/Agentic
claude plugin install launchpad@namrata-skills
```

Then, in the folder of the skill you want to launch, ask "help me launch this skill" or
run `/launchpad:launch-kit`. It runs the preflight checks, asks for your repo URL and
channels, and writes `launch/README-draft.md`, `launch/demo-script.md`,
`launch/posts.md` and `launch/checklist.md`.

The checker also runs on its own (Python 3.11+, no dependencies). It's a good CI step for
any skill repo:

```bash
python3 plugins/launchpad/skills/launch-kit/scripts/preflight.py path/to/skill-or-repo --strict
```

It checks the frontmatter (name rules, description length and "when to use" wording,
Claude Code-only fields that break portability), links to missing files, SKILL.md length,
marketplace entries against plugin manifests, and the launch basics: README install
command, demo media, and a license. `tests/test_skill_preflight.py` covers it.

How the example is laid out, and what to copy for your own repo:

| File | Role |
|---|---|
| [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json) | Makes this repo a marketplace called `namrata-skills` |
| [`plugins/launchpad/.claude-plugin/plugin.json`](../plugins/launchpad/.claude-plugin/plugin.json) | Plugin manifest |
| [`plugins/launchpad/skills/launch-kit/SKILL.md`](../plugins/launchpad/skills/launch-kit/SKILL.md) | The skill: portable frontmatter, numbered workflow, rules |
| [`.../references/channels.md`](../plugins/launchpad/skills/launch-kit/references/channels.md) | Long templates, read only when the skill runs |
| [`.../scripts/preflight.py`](../plugins/launchpad/skills/launch-kit/scripts/preflight.py) | Deterministic checks the skill runs instead of eyeballing |

## Sources

- Claude Code docs: [Skills](https://code.claude.com/docs/en/skills),
  [Create a plugin](https://code.claude.com/docs/en/plugins/create),
  [Create a marketplace](https://code.claude.com/docs/en/plugin-marketplaces),
  [Publish a plugin](https://code.claude.com/docs/en/plugins/publish)
- [Agent Skills specification](https://agentskills.io/specification)
- [skills.sh and the skills CLI](https://vercel.com/changelog/introducing-skills-the-open-agent-skills-ecosystem)
- [Anthropic's example plugins](https://github.com/anthropics/claude-code/tree/main/plugins)
- Examples mentioned: [Watermelon UI](https://github.com/WatermelonCorp/watermelon-platform),
  [awesome-claude-skills](https://github.com/BehiSecc/awesome-claude-skills),
  [best Claude Code skills of 2026](https://www.firecrawl.dev/blog/best-claude-code-skills)
