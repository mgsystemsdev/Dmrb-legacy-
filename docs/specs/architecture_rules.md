# DMRB Architecture Rules

Last updated: 2026-03-15
Status: Intended rules with current deviations documented

## 1. Purpose

This document defines the intended architectural standard for DMRB and records the most important places where the current codebase still deviates from that standard.

It should be used as both:

- the target architecture reference
- the stabilization checklist for bringing the codebase back into alignment

## 2. Intended Layered Architecture

The intended dependency flow remains:

`UI -> Services -> Domain -> Repositories -> Database`

### UI

Should:

- render screens
- collect user input
- call services

Should not:

- import repositories
- construct SQL
- own business rules

### Services

Should:

- coordinate operational workflows
- call repositories
- use domain logic
- own multi-entity write orchestration

Should not:

- import UI modules
- embed presentation rules

### Domain

Should:

- stay pure and dependency-free
- implement calculations and decision rules

Should not:

- access the database
- import Streamlit
- import services or repositories

### Repositories

Should:

- perform raw data access
- use parameterized SQL

Should not:

- contain workflow logic
- depend on services or UI

## 3. Data Rules

### Store facts, compute derived values

The following should remain computed:

- lifecycle phase
- readiness state
- DV / days since move-out
- DTBR / days to be ready
- board priority
- board summary metrics
- risk-radar scores

### Persist operational facts

The following belong in the database:

- turnover dates and overrides
- tasks and confirmations
- notes
- risk flags and SLA events
- import batches and row outcomes
- audit events

## 4. Current Deviations

These are active implementation deviations, not theoretical ones.

### 4.1 Application layer is mostly unused

`application/` exists, but most runtime flows are:

`UI -> service -> repository`

### 4.2 Repositories own DB connection access

The original architecture expected callers to pass connections into services and repositories.
The current implementation instead has repositories call `db.connection.get_connection()` directly.

### 4.3 Phase scope is enforced in the UI

Current global phase filtering is session-based and screen-level.
It is not yet enforced in services or repositories.

### 4.4 Some screens still shape operational logic

Several screens currently:

- compute metrics
- apply operational filters
- translate lifecycle into display-specific concepts

This is functional, but not the cleanest target architecture.

### 4.5 Bootstrap is schema-first, not migration-first

The codebase contains numbered migration SQL files, but application startup currently initializes from `db/schema.sql` through `ensure_database_ready()`.

## 5. Architectural Priorities

The highest-priority cleanup items are:

1. persist phase scope by property
2. move phase enforcement into services/repositories
3. reduce UI-owned operational filtering/metric logic
4. decide whether to activate the `application/` layer or remove the gap between docs and code
5. normalize database bootstrap and migration story

## 6. What Is Already in Good Shape

- domain logic is mostly pure
- repositories are clean SQL wrappers
- import behaviors are service-based rather than embedded in screens
- UI does not directly talk to repositories

## 7. Documentation Rule

When future docs describe the architecture, they should distinguish between:

- intended architecture standard
- current implementation reality

Without that distinction, the docs become misleading during stabilization.
