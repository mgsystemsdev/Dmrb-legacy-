# Manual QA — findings log

Use this file while running `MANUAL_QA_CHECKLIST.md`. **Do not put code fixes here** — only observations, classification, and checklist wording improvements.

---

## Run metadata (fill each session)

| Field | Value |
|--------|--------|
| **Date** | |
| **Branch / commit** | |
| **Property used** | |
| **DB writes** | on / off |
| **Notes** | e.g. seed data, env quirks |

---

## Severity (pick one — don’t overthink)

| Level | Use when |
|--------|----------|
| **blocker** | Core flow broken — e.g. can’t add turnover, export fails completely, app error blocks work |
| **high** | Wrong or untrusted data — counts wrong, SLA / Flag Bridge / Board mismatch, export ≠ UI |
| **medium** | UX confusion, unclear behavior, pass/fail ambiguous without harming trust in numbers |
| **low** | Polish, copy, minor friction |

---

## Finding template (copy per issue)

```text
### F-___

1. **Checklist item** — (quote or § reference, e.g. §3.1 Board, first bullet)

2. **Result:** pass / fail / unclear

3. **What happened** — (one to three sentences; facts only)

4. **Likely cause** — (hypothesis; optional if pass)

5. **Classification:** checklist issue / app bug / data issue

6. **Suggested checklist rewrite** — (only if classification is checklist issue or item was ambiguous; else “—”)

7. **Severity:** blocker / high / medium / low
```

---

## Static code verification (engineering) — 2026-03-30

**Task:** `dmrb-20260329-A2` — full write-up: `PHASE_1_LEGACY_TRUST_STATIC_SIGNOFF.md`.

| Field | Value |
|--------|--------|
| **Date** | 2026-03-30 |
| **Branch / commit** | (local workspace) |
| **Property used** | N/A — no browser session |
| **DB writes** | N/A |
| **Notes** | Code review + `MANUAL_QA_CHECKLIST.md` §2.3 / §3.8 aligned to code. `pytest`: 214 passed, 22 failed (fixture/DB state in this environment — see signoff doc). |

**Summary:** Board `data_editor` mutations persist via `board_table.py` → turnover/task services; unit detail autosave paths confirmed; import console and admin call real services; routed UI is not the `docs/legacy` skeleton app. **Operator must still run §4 Critical Truth Validation** in the browser for formal product sign-off.

---

## Findings — Run 1 (first full pass)

*Paste or write findings below. One `### F-001`, `### F-002`, … per distinct item.*

### F-001

1. **Checklist item** —

2. **Result:**

3. **What happened** —

4. **Likely cause** —

5. **Classification:**

6. **Suggested checklist rewrite** —

7. **Severity:**

---

## Quick table (optional summary)

| ID | § ref | Result | Severity | Classification | One-line summary |
|----|--------|--------|----------|------------------|------------------|
| F-001 | | | | | |

---

*After the run: triage — checklist edits go into `MANUAL_QA_CHECKLIST.md`; bugs get tracked separately when you are ready to fix.*
