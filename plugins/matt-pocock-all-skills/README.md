# Matt Pocock All Skills (Unofficial)

Includes all 38 skills under the upstream skills directory at commit `49dd158d1076134a641b33efb035946536778336`.
Source: https://github.com/mattpocock/skills

This is a personal snapshot, not an official release by Matt Pocock. Instruction bodies and supporting files are preserved. Claude-specific frontmatter is converted for Codex; explicit invocation is preserved through agents/openai.yaml. Skill folders are flattened for portable plugin discovery. MIT attribution is retained in LICENSE.

The official plugin ships engineering and productivity skills. This bundle additionally includes miscellaneous and in-progress skills because all skills were requested. Those workflows can be experimental or specific to Claude Code, Bash, or Matt's own projects; bundling does not make them native Windows or Codex compatible.

## Install

The workspace marketplace is at `.agents/plugins/marketplace.json`. Restart Codex, open the Plugins Directory, select Matt Pocock Local Skills, and install Matt Pocock All Skills (Unofficial). If the workspace source is not detected, register this workspace using `codex plugin marketplace add "C:\Users\kaust\Documents\ChatGPT\New project"`, then install through the app.

After installing, start a new chat and invoke `$setup-matt-pocock-skills` once per project. Use `$ask-matt` to choose a workflow. This snapshot does not update automatically.

## Included skills

- engineering: 20
- in-progress: 7
- misc: 4
- productivity: 7

- [ask-matt](skills/ask-matt/SKILL.md) (engineering)
- [code-review](skills/code-review/SKILL.md) (engineering)
- [codebase-design](skills/codebase-design/SKILL.md) (engineering)
- [diagnosing-bugs](skills/diagnosing-bugs/SKILL.md) (engineering)
- [domain-modeling](skills/domain-modeling/SKILL.md) (engineering)
- [grill-with-docs](skills/grill-with-docs/SKILL.md) (engineering)
- [implement](skills/implement/SKILL.md) (engineering)
- [implement-spec](skills/implement-spec/SKILL.md) (engineering)
- [improve-codebase-architecture](skills/improve-codebase-architecture/SKILL.md) (engineering)
- [pr](skills/pr/SKILL.md) (engineering)
- [prototype](skills/prototype/SKILL.md) (engineering)
- [research](skills/research/SKILL.md) (engineering)
- [retro](skills/retro/SKILL.md) (engineering)
- [setup-matt-pocock-skills](skills/setup-matt-pocock-skills/SKILL.md) (engineering)
- [tdd](skills/tdd/SKILL.md) (engineering)
- [to-spec](skills/to-spec/SKILL.md) (engineering)
- [to-tickets](skills/to-tickets/SKILL.md) (engineering)
- [triage](skills/triage/SKILL.md) (engineering)
- [wayfinder](skills/wayfinder/SKILL.md) (engineering)
- [wizard](skills/wizard/SKILL.md) (engineering)
- [chief-of-staff](skills/chief-of-staff/SKILL.md) (in-progress)
- [claude-handoff](skills/claude-handoff/SKILL.md) (in-progress)
- [loop-me](skills/loop-me/SKILL.md) (in-progress)
- [setup-ts-deep-modules](skills/setup-ts-deep-modules/SKILL.md) (in-progress)
- [writing-beats](skills/writing-beats/SKILL.md) (in-progress)
- [writing-fragments](skills/writing-fragments/SKILL.md) (in-progress)
- [writing-shape](skills/writing-shape/SKILL.md) (in-progress)
- [git-guardrails-claude-code](skills/git-guardrails-claude-code/SKILL.md) (misc)
- [migrate-to-shoehorn](skills/migrate-to-shoehorn/SKILL.md) (misc)
- [scaffold-exercises](skills/scaffold-exercises/SKILL.md) (misc)
- [setup-pre-commit](skills/setup-pre-commit/SKILL.md) (misc)
- [grill-me](skills/grill-me/SKILL.md) (productivity)
- [grilling](skills/grilling/SKILL.md) (productivity)
- [handoff](skills/handoff/SKILL.md) (productivity)
- [teach](skills/teach/SKILL.md) (productivity)
- [to-questionnaire](skills/to-questionnaire/SKILL.md) (productivity)
- [wait-what](skills/wait-what/SKILL.md) (productivity)
- [writing-for-agents](skills/writing-for-agents/SKILL.md) (productivity)
