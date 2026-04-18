> **Project-locked skill.** Requires `claude-system/` to be present at the project root (seeded via `~/agents/agent-system-base/init.sh`). Do not copy to `~/.claude/skills/`.

---
name: swarm
version: "1.0.0"
description: >
  Executable multi-agent plan: schema v2, API runner, merge conflicts, orchestrator integration.
  Global orchestrator: cd ~/.claude && python3 -m orchestrator --root <project>/claude-system (simulate | execute | handoff).
allowed-tools: Read, Write, Grep, Glob, Bash
---

# Mission

Run a **defined DAG** of agents (context → parallel tracks → merge), with **shared state on disk** and a **single merge artifact** (`merged.json` includes `conflicts[]`).

# Executable plan (source of truth)

- Plan file: `~/.claude/agents/plans/swarm_research.json` (or another plan under `~/.claude/agents/plans/`).
- Agent metadata: `~/.claude/agents/<name>.json` (`context`, `research`, `create`, `merge`). **`critical: true`** on `context` and `merge` aborts the run on failure.
- **Schema v2:** `~/.claude/schemas/agent_output_v2.schema.json` — runtime validation `orchestrator.models.validate_agent_output_v2`.

Required on every agent output:

- `status` (`success` | `failure`)
- `meta.run_id`, `meta.step_id`, `meta.schema_version` (`2`), `meta.agent` (must match top-level `agent`), `meta.timestamp` (ISO-8601)

On **success**: `research` needs `sources_checked[]`; `context` needs `docs_used[]`; `create` needs non-empty `artifacts[]`.

# Roles (swarm_research)

| Step | Agent   | Depends on | Parallel group | Produces              |
|------|---------|------------|----------------|------------------------|
| s1   | context | —          | 1              | `context.output.json`  |
| s2a  | research| s1         | 2              | `research.output.json` |
| s2b  | create  | s1         | 2              | `create.output.json`   |
| s3   | merge   | s2a, s2b   | 3              | `merged.json` (builtin)|

**Isolation:** read `context_for_<agent>.json` (capped **10KB**); full prior JSON paths are in `dependency_paths`.

# Controller (runnable)

```bash
RUNS_DIR="$(pwd)/runs/ephemeral"

cd ~/.claude
python3 -m orchestrator --runs-dir "$RUNS_DIR" --plan swarm_research --goal "<task>" --mode simulate
export ANTHROPIC_API_KEY=...
python3 -m orchestrator --runs-dir "$RUNS_DIR" --plan swarm_research --goal "<task>" --mode execute
```

Handoff waves:

```bash
RUNS_DIR="$(pwd)/runs/ephemeral"
cd ~/.claude
python3 -m orchestrator --runs-dir "$RUNS_DIR" --plan swarm_research --goal "<task>" --mode handoff
python3 -m orchestrator --runs-dir "$RUNS_DIR" --resume <run_id> --advance
python3 -m orchestrator --runs-dir "$RUNS_DIR" --resume <run_id> --finish
```

Details: `~/.claude/orchestrator/README.md`.

# Merge conflicts

Heuristic detection only (no silent resolution): artifact path collisions, low-similarity decisions between agents, output divergence. Review `merged.json` → `conflicts[]`.

# Final deliverable

- Valid v2 `*.output.json` + `merged.json` under `<project>/runs/ephemeral/<run_id>/`
- Optional narrative in `memory/agent-runs/<topic>.md`
