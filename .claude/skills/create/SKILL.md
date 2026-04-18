---
name: create
description: >
  Create reusable skills or agents when a repeatable workflow or multi-step pattern appears.
  Trigger when user asks to "make a skill", "create an agent", or repeats a process twice.
allowed-tools: Read, Write, Grep, Glob, Bash
---

# Mission

Identify repeatable workflows and convert them into structured, reusable skills or agents.

# Rules

- If task is simple + linear → create skill
- If task is multi-step + parallel → create agent
- Always output clean, reusable files

# Output

- `SKILL.md` or agent definition under `dmrb/dmrb-legacy/.claude/skills/<name>/` (repo root paths)
- Clear name, scope, tools, and usage

Orchestrator v2: on success, non-empty top-level `artifacts[]` (paths created or updated).
