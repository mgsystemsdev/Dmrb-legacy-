# DMRB System Blueprint

Last updated: 2026-03-15
Status: Current implementation snapshot

## 1. System Identity

DMRB is an operational turnover management system for apartment units.

It is not the PMS.
It is not accounting.
It is not leasing software.

It is the operational synchronization and execution layer that sits on top of PMS reports and turns those report signals into day-to-day turnover state.

Its current responsibilities are:

- ingest PMS report files
- reconcile report-authoritative fields with operational state
- maintain open turnover records
- track readiness, SLA pressure, and board priority
- support service-manager workflows across multiple operational screens
- provide diagnostics and repair workflows for bad or incomplete imports

Exports exist as a UI surface, but real export generation is not implemented yet.

## 2. Current Runtime and Deployment Reality

The active development environment is local PostgreSQL, not demo JSON and not an active Supabase deployment.

Current facts:

- the application boots against `DATABASE_URL`
- schema bootstrap is defined in `db/schema.sql`
- startup calls `db.connection.ensure_database_ready()`
- repositories talk directly to PostgreSQL through `psycopg2`
- Supabase remains an intended future target, but it is not the current active runtime surface

This project is no longer best described as a JSON-backed prototype. It is a PostgreSQL-backed Streamlit application in a stabilization phase.

## 3. Current Project Phase

The codebase is between initial system construction and deployment/export completion.

What is substantially in place:

- PostgreSQL schema and bootstrap
- repository and service layers for core entities
- board assembly and operational calculations
- import pipeline orchestration for the four PMS report types
- daily operations screens and navigation
- repair/diagnostic workflows for import exceptions
- work-order validation utilities

What remains incomplete or transitional:

- export generation
- persistent global phase scope
- full service/repository enforcement of phase scope
- fully implemented Pending FAS business logic
- end-to-end validation of SLA/risk/readiness metrics against real operating scenarios

## 4. Operational Model

Everything centers on the turnover lifecycle of a unit:

Move-Out -> Inspection / Work -> Final Walk -> Ready -> Move-In

The PMS provides external signals.
DMRB decides what to accept, what to protect, what to flag, and what to repair.

The system is designed to stay useful even when incoming PMS data is delayed, inconsistent, or incomplete.

## 5. Lifecycle Vocabulary

### 5.1 Preferred product-facing vocabulary

The preferred operational language remains:

- On Notice
- Vacant Not Ready
- Vacant Ready
- Ready
- Closed / Canceled

### 5.2 Current code vocabulary

The current domain lifecycle engine uses internal constants:

- `PRE_NOTICE`
- `ON_NOTICE`
- `VACANT_NOT_READY`
- `VACANT_READY`
- `OCCUPIED`
- `CLOSED`
- `CANCELED`

This means the docs and UI should distinguish between:

- product-facing operational status language
- internal computed lifecycle constants

Older shorthand such as NOTICE, VACANT, and SMI still appears in formatting and filters as derived display language.

## 6. Architecture: Intended Rule vs Current Implementation

### 6.1 Intended layered architecture

The intended architecture remains:

UI -> Services -> Domain -> Repositories -> Database

With these rules:

- UI should not contain business logic
- UI should not query repositories directly
- services should coordinate operational behavior
- domain should hold pure business rules and calculations
- repositories should do raw data access only

### 6.2 Current implementation reality

The repository layout mostly follows that shape, but there are active transitional deviations:

- `application/` exists but is effectively a placeholder; most flows are UI -> service directly
- repositories create and own their DB connection via `db.connection.get_connection()` instead of receiving connections from callers
- phase scope is enforced in selected UI screens, not in services or repositories
- some filtering, metric shaping, and scope logic still lives in screens
- imports are coordinated through services, but some behaviors documented as future design are not yet implemented

The codebase should therefore be described as architecture-aligned in direction, but not yet fully architecture-compliant.

## 7. Data Philosophy

The core data philosophy is still correct:

- store facts in PostgreSQL
- compute derived operational views in domain/service code

Examples of stored facts:

- properties, phases, buildings, units
- turnovers and dates
- tasks, notes, and risk flags
- SLA events
- import batches and import rows
- audit log entries
- unit movings
- turnover task override records

Examples of computed values:

- lifecycle phase
- DV / days since move-out
- DTBR / days to be ready
- readiness summary
- board priority
- board metrics
- risk radar score

## 8. Database Snapshot

The main schema currently contains:

- `property`
- `phase`
- `building`
- `unit`
- `turnover`
- `task_template`
- `task`
- `note`
- `risk_flag`
- `sla_event`
- `audit_log`
- `import_batch`
- `import_row`
- `turnover_task_override`
- `unit_movings`

Important current constraints and rules:

- one open turnover per unit through a partial unique index
- task type uniqueness per turnover
- append-only audit log
- import rows retain `raw_json`
- manual ready status constrained to `On Notice`, `Vacant Not Ready`, `Vacant Ready`
- move-in date cannot precede move-out date
- available date cannot precede move-out date

## 9. Import Authority Model

### 9.1 Report-authoritative fields

These are currently updated from PMS imports, subject to manual override protection where implemented:

- move-out date / scheduled move-out date
- move-in date
- available date
- availability status
- report-ready date

### 9.2 Operations-controlled fields

These remain operationally controlled:

- manual readiness decisions
- task execution and confirmation
- final walk completion
- other direct workflow edits made in the UI

### 9.3 Implemented report roles

Current implemented report behavior:

- `MOVE_OUTS`: primary turnover creator and scheduled move-out updater
- `PENDING_MOVE_INS`: updates move-in date only; does not create turnovers
- `AVAILABLE_UNITS`: updates readiness/availability fields and can create fallback turnovers for vacant units
- `PENDING_FAS`: rows are imported and recorded, but the legal confirmation/SLA reconciliation logic is still placeholder

## 10. Global Phase Scope

This is the highest-priority stabilization topic.

### 10.1 What exists now

- active phase scope is stored only in Streamlit session state as `selected_phases`
- phase selection is managed from Admin -> Phase Manager
- several UI screens apply the filter after loading property-wide data
- repositories and services do not enforce phase scope
- imports continue to operate at full-property scope

### 10.2 Screens that currently honor the session phase scope

The current code applies the phase scope in these places:

- sidebar top flags
- DMRB Board
- Morning Workflow
- Flag Bridge
- Risk Radar
- Property Structure

### 10.3 Screens that still work property-wide

Examples of current property-wide behavior:

- import ingestion
- import diagnostics and repair flows
- operations schedule service queries
- export screen messaging and placeholder downloads

### 10.4 Target direction

The future architecture should make phase scope:

- persistent
- property-specific
- enforced below the UI layer
- ignored for raw imports
- respected for operational exports

## 11. Property and Phase Model

Phases are not hard-coded in the current system.

The implementation already supports:

- per-property phase records in the database
- phase discovery/creation during unit resolution and unit import flows
- property-specific phase lists in the UI

This is one of the stronger areas of alignment between code and architecture.

## 12. Current Navigation and Screens

The active sidebar organization is:

### Quick Tools

- Add Turnover
- Unit Lookup
- DMRB AI Agent

### Daily Ops

- Morning WF
- DMRB Board
- Ops Schedule
- Flag Bridge
- Risk Radar
- W/O Validator

### Import and Reports

- Import Reports
- Repair Reports
- Export Reports

### Administration

- Report Operations
- Structure
- Admin

Important current details:

- `Import Reports` is the standalone import console
- `Report Operations` remains active and contains override conflicts, invalid data, and import diagnostics
- `Repair Reports` contains Missing Move-Out and FAS Tracker
- the AI Agent screen is placeholder UI only
- Export Reports is placeholder UI only

## 13. Stabilization Risks

The main active risks in the current codebase are:

- inconsistent phase-scope enforcement
- import duplicate/probe-batch behavior in the orchestrator
- placeholder Pending FAS behavior
- placeholder export generation
- service/repository architecture not yet fully normalized
- operational correctness still needing real-data validation for SLA, risk, and readiness

## 14. Canonical Bottom Line

The project today is:

- no longer a prototype
- not yet production-ready
- already a real PostgreSQL-backed operational system
- in a necessary stabilization phase

The most important current architectural task is to make global phase scope real and consistent without breaking full-property imports.
