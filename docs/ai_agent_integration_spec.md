# In-app AI assistant — integration spec (DMRB)

**Status:** Design / pre-implementation. **Engineering constraint:** Per `AGENTS.md` Phase 1, do not add LLM calls, AI endpoints, or worker AI logic until that phase explicitly allows it. This document defines *what to build when* the phase opens.

**Architecture anchor:** `DMRB_master_blueprint.md` §2.1.2–2.1.3 — user message → API enqueues job → worker fetches **tenant-scoped, read-only** context → LLM → stored reply; no LLM in the API request path; rate/cost limits in the worker.

---

## 1. Role and purpose

| Aspect | Definition |
|--------|------------|
| **Role** | Operational copilot for the **current tenant and property context** — answers questions and summarizes board state; does not replace the PMS or official reporting. |
| **Primary purpose** | Reduce time to insight: counts, lists, “what should I look at first?”, short briefings grounded in **allowed** API-sourced context only. |
| **Non-goals** | Executing writes, triggering imports, changing tasks/units, inventing numbers, accessing other tenants, or bypassing auth. |

**System prompt kernel (conceptual):**  
You are DMRB’s operational assistant. You only use the structured context provided (board summary, metrics, optional filters). If context is missing or insufficient, say so and suggest what the user can check in the app. Never fabricate unit counts or tenant data. Be concise; prefer bullets for lists. Role: helpful operator-facing assistant, not legal/financial advisor.

---

## 2. Core prompts (layers)

1. **System** — Identity, boundaries, data rules (above), output shape (short paragraphs + bullets), refusal patterns (“I don’t have that in the provided context”).
2. **Developer / tool policy** (future) — If tools exist later, list allowed read-only tools and forbid destructive actions. Until then: text-in, text-out from worker-assembled context only.
3. **User** — Raw question or command in natural language.
4. **Context injection** (worker-built, not user-visible) — Sanitized JSON or narrative summary: e.g. property name, date, vacancy/pending counts, top flags, SLA highlights — **only** fields the worker is allowed to attach for that JWT/tenant.

**Starter user intents → prompt shaping (examples):**

- *Morning briefing* → prepend instruction: “Summarize priorities for today in ≤8 bullets; lead with risk/SLA.”
- *Counts* → “Answer with numbers from context only; cite ‘as of’ from context timestamp if present.”
- *Explain screen* → “Explain what this view is for in DMRB terms; do not guess current numbers without context.”

Refine these in-app once a minimal chat UI + stub worker context exists.

---

## 3. User interaction (tone, flow, limits)

| Dimension | Recommendation |
|-----------|----------------|
| **Tone** | Direct, professional, calm; no slang pile-ons; mirror operator urgency without alarmism. |
| **Flow** | Message in → **202 + job_id** → poll (or push) for completion → show reply; show “working” state; allow follow-up in same session. |
| **Length** | Default max reply tokens bounded in worker config; soft cap on user message length (blueprint: length + rate limits). |
| **Errors** | Structured error to UI: rate limit, context build failure, LLM failure — never silent empty states. |

**Flexibility vs control:** High control on **facts** (only from injected context); moderate flexibility on **wording and prioritization** (how to order bullets, what to emphasize).

---

## 4. Where and when the agent runs

| Trigger | Behavior |
|---------|----------|
| **Dedicated AI / Assistant screen** | Primary surface; full chat history for session. |
| **Optional later: contextual entry** | e.g. “Ask about this board” prefilled with property id — still submits through same enqueue path; no inline blocking calls. |
| **Not allowed (v1)** | Auto-running on every page load, or running inside import/upload request path. |

---

## 5. Responsibilities vs out of scope

**Should handle**

- Natural-language Q&A over **provided** board/metrics context.
- Briefings and “what to look at” style prioritization **grounded in that context**.
- Explaining DMRB concepts (what a turnover is, what a flag means) at a high level.

**Should not handle (until explicitly designed)**

- Creating/updating tasks, units, or imports.
- Answering from memory of prior sessions without persisted, tenant-scoped store.
- Cross-tenant analytics or “compare all my properties” unless context explicitly includes multiple allowed properties.

---

## 6. Guardrails and adaptation

- **Tenant / JWT:** All context assembly keyed to authenticated tenant (and property scope from token or query).
- **PII:** Minimize free-text PII in context packs; prefer aggregates and IDs only where needed.
- **Adaptation by user state:** Optional later: role-aware phrasing (operator vs admin) **without** changing which data the worker may load — same allowlist, different system prompt suffix.
- **Cost:** Worker-side rate limits, token caps, and optional daily quota per tenant.

---

## 7. Testing and refinement

1. **Fixture contexts** — Save 3–5 anonymized context payloads; run regression prompts (“morning briefing”, “how many vacant”, edge: empty board).
2. **In-app** — Same flows with real JWT; compare hallucination rate when context is intentionally sparse.
3. **Red-team** — Prompts asking for other tenants, SQL, or “mark all complete”; expect refusals.

---

## 8. Open questions → proposed defaults

| Question | Proposed default |
|----------|------------------|
| Specific tasks for users? | Start with Q&A + morning/daily briefing + explain-this-metric; expand after usage data. |
| Constraints / guardrails? | Read-only context pack; no tools v1; refusals on missing data; tenant-scoped worker. |
| Adapt by user state? | Yes, lightly (role suffix + property context); no extra data paths without product sign-off. |

---

## 9. Implementation checklist (when phase allows)

- [ ] API: enqueue-only AI job; validate body (session id, message, limits).
- [ ] Worker: build context from read-only repos/services; call provider; persist result; metrics.
- [ ] Frontend: dedicated assistant route; job polling UX; errors.
- [ ] Ops: rate limits, logging, cost alerts.
