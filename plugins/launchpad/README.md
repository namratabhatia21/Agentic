# Launchpad

Get your Claude Code skill ready to launch, and get the README, demo script and posts
written for you.

Launchpad is a Claude Code plugin with one skill, `launch-kit`. Point it at a skill,
plugin or repo and it:

1. **Runs preflight checks**: frontmatter, name rules, description length and trigger
   wording, broken links, portability to claude.ai and other agents, marketplace and
   manifest consistency, README install command, demo media, license.
2. **Writes a launch kit** into `launch/`: a README draft in the structure that converts
   visitors, a shot list for a 20-40 second Reel / TikTok / Short, posts written for X,
   LinkedIn, Instagram, Reddit and Hacker News, and a dated launch checklist.

## Install

From the plugin marketplace in this repo:

```bash
claude plugin marketplace add namratabhatia21/Agentic
claude plugin install launchpad@namrata-skills
```

With the cross-agent skills CLI:

```bash
npx skills add namratabhatia21/Agentic
```

Or by hand: copy `skills/launch-kit/` to `~/.claude/skills/launch-kit/`.

## Use it

```text
/launchpad:launch-kit ./my-skill
```

Or just ask: "I built a skill for X. Help me launch it." Claude picks the skill up from
its description.

The checker also runs on its own, with no dependencies beyond Python 3.11:

```bash
python3 skills/launch-kit/scripts/preflight.py path/to/your-skill-or-repo
python3 skills/launch-kit/scripts/preflight.py . --strict   # fail on warnings, for CI
```

## Files

```
launchpad/
├── .claude-plugin/plugin.json      plugin manifest
└── skills/launch-kit/
    ├── SKILL.md                    instructions Claude follows
    ├── references/channels.md      README, video and per-channel templates (read on demand)
    └── scripts/preflight.py        the checker
```

## License

MIT
