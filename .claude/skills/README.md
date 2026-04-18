# Claude Code skills (this repo)

> **DEPRECATED LOCATION.** Skills have been migrated:
> - `context`, `create`, `research` → `~/.claude/skills/` (global)
> - `swarm` → production checkout’s `.claude/skills/swarm/` (separate tree from this legacy clone)
>
> These copies are kept for reference only. Claude Code discovers skills from the project root `.claude/skills/` and `~/.claude/skills/`, not from this nested path.

Project-local skills live here: `.claude/skills/<skill-name>/SKILL.md` at **this** repo root. They apply when you use **Claude Code** in this checkout and typically override global skills of the same name in `~/.claude/skills/`. A **prod** checkout is independent—its `.claude/skills/` is not shared automatically.

| Skill     | Use when |
|-----------|----------|
| `create`  | User wants a new reusable skill/agent pattern |
| `context` | Need current docs or API behavior before coding |
| `swarm`   | Executable DAG + `cd claude-system && python3 -m orchestrator` (see `claude-system/agents/plans/`, `claude-system/orchestrator/README.md`) |
| `research`| Multi-source technical investigation |

**Experimental agent teams:** set `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in the environment that launches `claude`, then restart. Parallel orchestration still needs clear plans and shared output paths (see `swarm`).

See root `CLAUDE.md` for DMRB project rules; skills add workflow playbooks on top of that.
