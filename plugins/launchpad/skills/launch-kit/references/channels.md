# Channel formats

Templates for each piece of the launch kit. Fill them from the target's real files and
replace every `<placeholder>`. Cut any section that has nothing true to say.

## README

People decide in about five seconds whether to keep reading. Order matters:

```markdown
# <name>

<promise line: what it does, for whom, in 12 words or fewer>

<demo GIF or video: the first thing under the title, showing the result>

## Install

<every working route: marketplace, npx skills add, manual copy. Copy-paste ready>

## What it does

| Without <name> | With <name> |
|---|---|
| <generic result Claude gives by default> | <what the skill changes> |

## Try it

<three copy-paste prompts, from simplest to most impressive>

## How it works

<3-5 sentences. Link to SKILL.md for the curious>

## Limits

<what it doesn't do yet. Admitting this builds trust and attracts contributors>

## License

<license>
```

Also set these on the GitHub repo page:

- **About / description**: the promise line, plus the website or demo link.
- **Topics**: `claude-code`, `claude-skills`, `agent-skills`, `claude-code-plugin`, plus
  2-4 for the domain (`react`, `video`, `remotion`, `seo` ...). Topics are how people
  browsing GitHub find the repo.
- **Social preview** (Settings > General): a 1280x640 image with the name, the promise and
  a screenshot. Every link shared on X, LinkedIn or Slack shows it.
- **Release**: tag `v1.0.0` with short notes, so there is something to announce later.
- **Pin** the repo on the GitHub profile.

## Demo video

The video is the main asset. Instagram, TikTok and YouTube Shorts audiences discover
skills by seeing a result, not by reading about it.

**Vertical cut (9:16, 20-40 s)** for Reels, TikTok and Shorts:

| Time | Shot | On-screen text |
|---|---|---|
| 0-2 s | The finished result, full screen | The hook: "Claude made this from one sentence" |
| 2-6 s | Optional: the same prompt without the skill (generic output) | "Without the skill" |
| 6-20 s | Typing the prompt or `/command`, then Claude working, sped up 4-8x | "With <name>" |
| 20-30 s | The result: scroll, click, play | One concrete detail that stands out |
| last 3 s | Repo name and install line on screen | The CTA: "Free and open source. Link in bio" |

**Landscape cut (16:9, 45-90 s)** for X, LinkedIn and YouTube: same story, with a
little more of how it works.

**README GIF**: the 6-30 s part only, 10 MB or less, 800-1200 px wide. Terminal-only demos
can be scripted with [vhs](https://github.com/charmbracelet/vhs) so they can be
re-recorded.

Recording tips:
- Use a large terminal or editor font (20 pt or more) and crop to where the action is.
- Burn in captions, because most people watch with the sound off.
- Show real output, never a mock-up. Re-record rather than edit the result.

## X (Twitter)

A thread of 4-5 posts. Attach the video to the first one.

1. Hook and video: the result, in one line. "I taught Claude Code to <outcome>. One command."
2. The problem: what was annoying before, in a sentence or two.
3. How it works: two or three short lines, or a screenshot of the `SKILL.md`.
4. Install: the one-liner in a code-style block.
5. The link to the repo, plus a request for feedback or ideas.

Many creators put the repo link in a reply instead of the first post. Tag the authors of
the tools the skill builds on only when the skill is actually about their tool.

## LinkedIn

A short first-person story, 120-200 words, with the video uploaded natively:

- Line 1 (shown before "see more"): the outcome or a surprising number you measured.
- The problem you kept hitting.
- What you built and one thing you learned building it.
- Install or try it. Put the link in the post or the first comment.
- Up to three hashtags at the end.

## Instagram / TikTok caption

- 1-2 lines that restate the hook.
- A CTA: "Link in bio", or "Comment SKILL and I'll send the link" (only if the user will
  actually reply to those comments or uses an automation tool the platform allows).
- 3-5 hashtags, such as `#claudecode #aitools #webdev`, plus one for the domain.
- Pin a comment with the repo name, because captions get truncated.

## Reddit

Good places: r/ClaudeAI, r/ClaudeCode, and one niche subreddit where the skill's users are
(r/webdev, r/reactjs, r/SideProject, r/videoediting ...). **Read each subreddit's
self-promotion rules first** and post to one subreddit per day at most.

- Title: what it does, plainly. "I made a Claude Code skill that <outcome>". No clickbait.
- Body: why you built it, the GIF or video, install, known limits, and what feedback you
  want. Say that you're the author.
- Reply to every comment for the first few hours. That is where most of the reach comes from.

## Hacker News

Only for skills that are technically interesting (a new technique, a clever script, real
numbers).

- Title: `Show HN: <name> – <promise>`, linking to the repo.
- Post a first comment yourself: the backstory, how it works, what's next. Be modest and
  technical, and answer every question.

## Directories and lists

| Where | How |
|---|---|
| [skills.sh](https://skills.sh) | Skills installed with `npx skills add <owner>/<repo>` show up there, ranked by installs. Put that command in the README so installs count |
| Anthropic's plugin directory | Submit the plugin at [claude.ai/directory/manage](https://claude.ai/directory/manage) (needs a paid claude.ai plan; each version is reviewed). A listing reaches claude.ai, Cowork and Claude Code |
| "Awesome" lists on GitHub | Search GitHub for `awesome claude skills` and open a one-line PR to each active list, following its CONTRIBUTING rules |
| Community plugin directories | Some community sites list public GitHub repos that ship a `.claude-plugin/marketplace.json`. Search for your repo on them and submit it where they take submissions |
| Product Hunt | Only for a bigger launch with a polished demo and a landing page |

## Launch checklist

```markdown
## Before launch (T-7 to T-1)
- [ ] preflight passes with 0 errors; `claude plugin validate` passes
- [ ] fresh install works, tested in a clean container or another machine
- [ ] trigger test: 3 prompts that should use the skill do; 2 near-misses don't
- [ ] README with GIF, repo topics, social preview, v1.0.0 release
- [ ] vertical and landscape videos exported, captions burned in

## Launch day (T-0)
- [ ] post the vertical video on the main channel (Instagram / TikTok)
- [ ] X thread, LinkedIn post
- [ ] one subreddit (the best fit)
- [ ] spend 2-3 hours replying to every comment

## First week (T+1 to T+7)
- [ ] a second subreddit or Show HN, only if day one got traction
- [ ] PRs to awesome lists; directory submission
- [ ] turn feedback into GitHub issues; ship v1.1 with something users asked for
- [ ] announce v1.1 ("you asked, I shipped")

## Ongoing
- [ ] one short video per new use case or feature
- [ ] check GitHub Insights > Traffic weekly: which referrers send stars?
```
