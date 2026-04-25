# DMRB Legacy (Digital Make Ready Board)

## What it is
The Digital Make Ready Board (DMRB) is a turnover management application for apartment operations (Billingsley Company). It provides real-time visibility into apartment turnover status, task pipelines, and property-management report imports, helping teams coordinate "make-ready" tasks between vendors and managers.

---

## 🏗️ Core Architecture & Dependencies

### The Dependency Chain (The "Golden Thread")
The system follows a strict linear dependency. If the start of the chain fails, the entire system is blocked:
`Unit Master (Source of Truth for Units) → Turnover → Tasks (Execution Engine) → Board (Readiness/Visibility)`

### Data Flow
`Import → Unit Master → Turnover → Tasks → Board → UI`

### Separation of Planes
- **Control Plane (Admin):** Manages Unit Master, Phase Scope, and System Settings.
- **Execution Plane (Tasks):** Manages the actual work, driving readiness %, lifecycle phases, and blocking logic.

### 💎 Source of Truth (SSOT)
- **Unit Master:** Authoritative source for all units.
- **Phase Manager:** Authoritative source for scoped phases.
- **Task System:** Authoritative source for execution state and readiness.
- **Board:** A derived, non-authoritative view.

---

## 📋 System Requirements (R1 - R20)

### 🔴 1. Entry Layer
- **R1: Unit Master (Source of Truth):** Central system for all units; enforces property → phase → building integrity.
- **R2: Unit Master Import (CRITICAL BLOCKER):** Reliable CSV parsing with pre-validation, dry-run mode, and row-level error reporting.

### 🟠 2. Data Model Layer
- **R3: Turnover System:** Dependent on Unit Master; attaches lifecycle state to units.
- **R7: Phase Manager (Scope Control):** Persists active phases per property as a global filter.
- **R8: Phase Scope Synchronization:** ALL UI elements must use scoped phases; handle loading/empty/invalid states.

### 🟡 3. Execution Layer
- **R4: Task System (Engine):** Backend FSM driving readiness %, lifecycle transitions, and Final Walk eligibility.
- **R5: Task Templates + Generation:** Auto-generate task pipelines per property/phase/face on turnover creation.
- **R6: Task Manager (Execution UI):** Dedicated UI for status updates, assignments, and FSM debugging (separate from Admin).
- **R8 (Repeat/Integrate):** Turnover → Task integration with auto-generation and lifecycle tracking.

### 🟣 4. Configuration Layer
- **R9: Face Manager:** Configures workflow structure and pipeline grouping per property/face.

### 🔵 5. Stability & Derived Systems
- **R10: Board System (Visibility):** Displays readiness and lifecycle state; must never break due to backend failures.
- **R11: Reconciliation Engine (Healing):** Idempotent board rebuild that tolerates missing/incomplete data.
- **R12: Observability / Debug Layer:** Exposure of import results, reconciliation behavior, and task generation.
- **R13: Error Handling Standard:** Structured errors for all operations; no silent failures.

### 🔐 6. Environment & Auth Layer
- **R14: DB-Based Authentication:** Use `app_user` table (Argon2); no env-based fallback in production.
- **R15: Bootstrap Logic:** Reliable setup flow when the user table is empty; no reliance on inconsistent env state.

### 🧠 7. Architecture Rules (R16 - R20)
- **R16: Layered Architecture:** UI → Services → Repositories → Domain.
- **R17: Domain Purity:** `domain/` logic contains no DB or I/O.
- **R18: SSOT Enforcement:** Strict adherence to authoritative sources for units, scope, and execution.
- **R19: State Management Contract:** React Query for server state; Zustand for UI state.
- **R20: Plane Separation:** Admin (Control) vs. Tasks (Execution).

---

## 🚨 TRUE BLOCKERS (CRITICAL PATH)
1. **R2 — Unit Master Import:** The entry point is unstable; parsing errors are invisible.
2. **R6 — Task Execution UI:** No control layer for the execution engine; work cannot be managed from the UI.
3. **R8 — Phase Manager Sync:** Global state inconsistencies across UI components.

---

## 🛠️ Stack & Reality
**Frontend:** React (TS), Vite, Tailwind, AG Grid, TanStack Query, Zustand.
**Backend:** FastAPI (Python 3.13), Uvicorn.
**Database:** PostgreSQL (Raw SQL).

**Operability Status:**
The system is runnable (backend + UI load), but **not reliably operable end-to-end** due to gaps in input validation, execution visibility, and global state consistency.

---

## 🚦 Current Focus & Roadmap
1. **Fix Unit Master Import (R2):** Enable reliable data entry with dry-run/validation.
2. **Implement Task Execution UI (R6):** Unlock the execution plane.
3. **Stabilize Phase Manager (R7/R8):** Ensure global synchronization of scope.

---

## 📝 Decisions Log
- **2026-04-24** — Canonical Requirements Finalized: Documented R1-R20 and identified the "Golden Thread" dependencies.
- **2026-04-01** — React SPA (Path B): Chose React over HTMX/Streamlit.
- **2026-03-20** — No ORM Policy: Raw SQL for performance and control.
