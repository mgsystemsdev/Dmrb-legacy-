**DMRB Rebuild Roadmap**

Status note: This is a historical target-state roadmap. Several items in this file no longer match the exact current implementation because the project entered a PostgreSQL stabilization phase. Use it as roadmap intent, not as a current-state architecture description.

Phase-by-Phase Execution Plan with Prompts

Each step includes the exact prompt to use in the rebuild chat

Version 1.0 --- March 2026

Rebuild Overview

The rebuild follows 8 phases in strict order. Each phase depends on the
previous one. Do not skip ahead.

  ---------------- ---------------------------------- --------------------
  **Phase**        **What Gets Built**                **Chat Role**

  1\. Repository   Empty repo, folder structure,      Any chat
  Setup            requirements, app.py shell, config 

  2\. Schema       PostgreSQL schema, constraints,    Schema Architect
  Design           indexes, initial migration,        
                   connection module                  

  3\. Domain Logic lifecycle.py, enrichment.py,       Domain Architect
                   risk_engine.py, sla_engine.py,     
                   risk_radar.py, unit_identity.py    

  4\. Core         turnover_service, task_service,    Service Builder
  Services         risk_service, sla_service,         
                   note_service, property_service,    
                   unit_service                       

  5\. Import       Orchestrator, validation,          Import Engineer
  Pipeline         move_outs, move_ins,               
                   available_units, pending_fas, task 
                   instantiation                      

  6\. Board and    board_query_service, enrichment    Board & Query
  Query Layer      pipeline, cache layer              Builder

  7\. UI Screens   All Streamlit screens, routing,    UI Engineer
                   auth, components, session state    

  8\. Verification Tests, logging, performance        Verification
  and Hardening    review, deployment prep            Engineer
  ---------------- ---------------------------------- --------------------

Phase 1 --- Repository Setup

Create the empty project structure that all subsequent phases build
into.

Step 1.1 --- Create Folder Structure

Create all folders from the System Map with empty \_\_init\_\_.py files.

**PROMPT:**

> Create the DMRB project folder structure exactly as defined in the
> System Map document (Section 2). Create all directories with empty
> \_\_init\_\_.py files. Create an empty app.py, an empty
> requirements.txt, and a .streamlit/secrets.toml placeholder. Do not
> add any logic yet. The goal is an empty skeleton that matches the
> System Map perfectly. List every folder and file you created.

Step 1.2 --- Create requirements.txt

Define Python dependencies for the project.

**PROMPT:**

> Create requirements.txt for the DMRB project. The stack is: Streamlit
> (frontend), psycopg2-binary (Supabase PostgreSQL), pandas (data
> handling), openpyxl (Excel import/export). Add only what is needed. No
> ORM. No FastAPI. No unnecessary packages.

Step 1.3 --- Create config/settings.py

Configuration module that resolves from environment first, Streamlit
secrets as fallback.

**PROMPT:**

> Create config/settings.py following the Architecture Rules (Section
> 9). It must resolve database URL, auth credentials, and feature flags
> from environment variables first, with Streamlit secrets as a
> fallback. It must not import Streamlit at the top level. It must
> detect Streamlit availability at runtime. Include a get_setting(key,
> default=None) function.

Step 1.4 --- Create app.py Shell

Thin Streamlit entrypoint under 50 lines.

**PROMPT:**

> Create app.py as the Streamlit entrypoint. It must be under 50 lines.
> It should: set page config, initialize session state (import from
> ui/state/session.py), call backend bootstrap (import from
> ui/data/backend.py), render navigation sidebar (import from
> ui/components/sidebar.py), and call the router (import from
> ui/router.py). All of these imports will be placeholders for now. No
> business logic in this file.

**✅ CHECKPOINT: Repository skeleton exists. All folders match the
System Map. app.py is under 50 lines. Config resolves from
environment.**

Phase 2 --- Schema Design

Design and implement the PostgreSQL schema for Supabase.

Step 2.1 --- Design Core Tables

Create the schema for the main operational entities.

**PROMPT:**

> Read Blueprint Sections 2, 7, and 10, and Architecture Rules Section
> 3. Design the PostgreSQL schema for the DMRB core tables: property,
> phase, building, unit, turnover, task_template,
> task_template_dependency, task, task_dependency, note, risk_flag,
> sla_event, audit_log, import_batch, import_row. Follow the data
> philosophy: store facts, compute everything else. Include all
> constraints from Blueprint Section 7 (one open turnover per unit,
> turnover requires move-out, task unique per type per turnover, etc.).
> Include created_at and updated_at on all tables. Include property_id
> on all operational tables. Write this as db/schema.sql.

Step 2.2 --- Create Connection Module

**PROMPT:**

> Create db/connection.py. It must: provide get_connection() that
> creates a PostgreSQL connection using the database URL from
> config/settings.py; set prepare_threshold=None for Supabase
> transaction pooler compatibility; provide ensure_database_ready() that
> applies schema.sql and migrations at startup. Connection module must
> not import Streamlit.

Step 2.3 --- Create Initial Migration

**PROMPT:**

> Create db/migrations/001_initial.sql. This is the baseline migration
> that creates all tables defined in schema.sql. It should be idempotent
> (use IF NOT EXISTS where appropriate). Include a schema_version table
> to track applied migrations.

Step 2.4 --- Create Repository Shells

**PROMPT:**

> Create empty repository modules in db/repository/ for each entity:
> turnovers.py, tasks.py, units.py, properties.py, imports.py, risks.py,
> sla.py, notes.py, audit.py. Each file should have a module docstring
> explaining its responsibility (from the System Map). Include
> placeholder function signatures with pass bodies for the most
> important operations. Do not implement the SQL yet.

**✅ CHECKPOINT: Schema exists in schema.sql. Connection module works
with Supabase. Migration applies cleanly. Repository shells exist for
all entities. Schema enforces all invariants from Blueprint Section 7.**

Phase 3 --- Domain Logic

Implement pure business rules with zero external dependencies.

Step 3.1 --- Unit Identity

**PROMPT:**

> Create domain/unit_identity.py. Implement: normalize_unit_code(raw)
> that strips prefixes, uppercases, collapses whitespace;
> parse_unit_parts(normalized) that splits into phase_code,
> building_code, unit_number; compose_identity_key(phase, building,
> unit_number). Reference the Blueprint Section 2.2 for unit identity
> rules. Zero external imports.

Step 3.2 --- Lifecycle Engine

**PROMPT:**

> Create domain/lifecycle.py. Implement:
> derive_lifecycle_phase(move_out_date, move_in_date, closed_at,
> canceled_at, today) that returns the lifecycle phase (NOTICE,
> NOTICE_SMI, VACANT, SMI, MOVE_IN_COMPLETE, STABILIZATION, CANCELED,
> CLOSED); derive_nvm(phase) that returns the NVM display label;
> effective_move_out_date(row) that selects the canonical move-out using
> the precedence: manual override \> legal confirmed \> scheduled \>
> base. Reference Blueprint Section 3. Zero external imports except
> datetime.

Step 3.3 --- Enrichment Engine

**PROMPT:**

> Create domain/enrichment.py. Implement the board row enrichment
> pipeline: compute DV (business days since effective move-out), DTBR
> (business days to move-in), task completion ratio, current task, next
> task, stall detection, operational state labels (Move-In Risk, QC
> Hold, Work Stalled, In Progress, Apartment Ready, Pending Start),
> attention badges, and readiness flags (is_unit_ready,
> is_ready_for_moving). Reference Blueprint Sections 3, 4, 5. The main
> function enrich_row(turnover_dict, unit_dict, tasks_list, notes_list,
> today) should return an enriched dictionary. Zero external imports
> except datetime.

Step 3.4 --- Risk Engine

**PROMPT:**

> Create domain/risk_engine.py. Implement evaluate_risks(move_in_date,
> move_out_date, today, tasks, wd_present, wd_supervisor_notified,
> has_data_integrity_conflict, has_duplicate_open_turnover,
> report_ready_date, manual_ready_confirmed_at) that returns a list of
> {risk_type, severity} dicts. Risk types: QC_RISK, WD_RISK,
> CONFIRMATION_BACKLOG, EXECUTION_OVERDUE, EXPOSURE_RISK,
> DATA_INTEGRITY, DUPLICATE_OPEN_TURNOVER. Reference Blueprint Sections
> 5.2 and 7. Zero external imports except datetime.

Step 3.5 --- SLA Engine

**PROMPT:**

> Create domain/sla_engine.py. Implement
> evaluate_sla_state(move_out_date, manual_ready_confirmed_at, today,
> open_breach_exists) that returns {breach_active, should_open_breach,
> should_close_breach}. SLA threshold is 10 days. Once
> manual_ready_confirmed_at is set, breach cannot reopen (stop
> dominance). Reference Blueprint Sections 5.2 and 7.4. Zero external
> imports except datetime.

Step 3.6 --- Risk Radar

**PROMPT:**

> Create domain/risk_radar.py. Implement
> score_enriched_turnover(enriched_row) that computes a numeric
> risk_score and risk_level (LOW, MEDIUM, HIGH) from the enriched
> turnover data. Reference Blueprint Section 5. Zero external imports.

**✅ CHECKPOINT: All domain files exist with zero external dependencies.
Each file can be imported and tested without database or Streamlit.
Lifecycle phases match Blueprint Section 3.2. Enrichment produces all
fields listed in Blueprint Section 4. Risk types match Blueprint Section
5.**

Phase 4 --- Core Services

Implement business orchestration services. Build in this order because
each service depends on the previous ones.

Step 4.1 --- Repository Implementation

**PROMPT:**

> Implement the repository modules created in Phase 2. Start with
> db/repository/turnovers.py (insert, update, get_by_id,
> get_open_by_unit, list_open, close, cancel), then tasks.py (insert,
> update_fields, get_by_turnover, get_for_turnover_ids, template
> operations), then units.py, properties.py, imports.py, risks.py,
> sla.py, notes.py, audit.py. All queries must be parameterized. Each
> function receives a connection as its first argument. One entity per
> file. No business logic in repositories. Reference System Map Section
> 8 for each file\'s responsibility.

Step 4.2 --- Property and Unit Services

**PROMPT:**

> Implement services/property_service.py and services/unit_service.py.
> Property service: insert_property, list_properties, resolve_phase,
> resolve_building, list_phases, list_buildings. Unit service:
> list_units, get_unit_by_identity_key. These are foundational services
> used by imports and turnovers. Reference System Map Section 6.

Step 4.3 --- Turnover Service

**PROMPT:**

> Implement services/turnover_service.py. Must include:
> create_turnover_and_reconcile (create turnover, instantiate tasks,
> reconcile SLA and risks), update_turnover_dates (with manual override
> semantics and SLA recalculation), set_manual_ready_status,
> confirm_manual_ready, clear_manual_override,
> reconcile_after_task_change, attempt_auto_close (after move-in + 14
> days if no critical risks). Every significant change writes to
> audit_log. Reference Blueprint Section 7.1 for turnover invariants.

Step 4.4 --- Task Service

**PROMPT:**

> Implement services/task_service.py. Must include: update_task_fields
> (handles status transitions: NOT_STARTED to SCHEDULED to IN_PROGRESS
> to COMPLETED), audit logging for every field change, and calling
> turnover_service.reconcile_after_task_change after updates. Enforce
> task transition rules from Blueprint Section 4.1. Reference System Map
> Section 6.

Step 4.5 --- Risk and SLA Services

**PROMPT:**

> Implement services/risk_service.py and services/sla_service.py. Risk
> service: reconcile_risks_for_turnover (call domain risk_engine,
> compare with current risk_flags, upsert new risks, resolve removed
> risks, audit changes). SLA service: reconcile_sla_for_turnover (call
> domain sla_engine, manage sla_event rows, enforce stop dominance,
> audit changes). Reference Blueprint Sections 5.2 and 7.4.

Step 4.6 --- Note Service

**PROMPT:**

> Implement services/note_service.py. Create note, resolve note, get
> notes by turnover. Simple service. Reference System Map Section 6.

Step 4.7 --- Application Workflows and Commands

**PROMPT:**

> Implement application/commands/write_commands.py with dataclasses:
> UpdateTurnoverStatus, UpdateTurnoverDates, UpdateTaskStatus,
> CreateTurnover, ClearManualOverride. Implement
> application/workflows/write_workflows.py with workflow functions that
> accept commands, obtain connections, call the appropriate services,
> commit transactions, and invalidate caches. Reference System Map
> Section 7.

**✅ CHECKPOINT: All core services implemented. Turnover creation works
with task instantiation. Task status transitions work. Risk and SLA
reconciliation works. Audit logging works. Application workflows connect
commands to services.**

Phase 5 --- Import Pipeline

Build the report ingestion system. This is the most complex subsystem.

Step 5.1 --- Validation Modules

**PROMPT:**

> Implement services/imports/validation/file_validator.py and
> schema_validator.py. File validator checks extension and non-empty
> file. Schema validator checks required columns and data types per
> report type (MOVE_OUTS, PENDING_MOVE_INS, AVAILABLE_UNITS,
> PENDING_FAS). Return structured validation diagnostics. Reference
> Architecture Rules Section 4.

Step 5.2 --- Import Common Helpers

**PROMPT:**

> Implement services/imports/common.py. Shared helpers:
> normalize_unit_code (uses domain/unit_identity), ensure_unit (resolve
> or create unit), find_or_create_turnover_for_unit (check for open
> turnover, create if missing via turnover_service), append_diagnostic
> (record per-row diagnostic). Reference System Map Section 6.

Step 5.3 --- MOVE_OUTS Importer

**PROMPT:**

> Implement services/imports/move_outs.py. This is the primary turnover
> creator. For each row: ensure unit exists, check for open turnover. If
> no open turnover, create one. If open turnover, reconcile move-out
> date respecting manual overrides and legal confirmations. Record
> import_row with validation status. Post-process: increment
> missing_moveout_count for turnovers not in this batch; auto-cancel
> after 2 consecutive misses. Reference Blueprint Sections 6.2 and 7.3.

Step 5.4 --- Other Importers

**PROMPT:**

> Implement services/imports/move_ins.py (update move_in_date on
> existing turnovers), services/imports/available_units.py (update
> availability status, available_date, report_ready_date with
> override-aware logic), and services/imports/pending_fas.py (set legal
> confirmation fields and reconcile SLA). None of these create
> turnovers. All record import_row outcomes. Reference Blueprint Section
> 6.2 for each report\'s behavior.

Step 5.5 --- Task Instantiation

**PROMPT:**

> Implement services/imports/tasks.py. Function:
> instantiate_tasks_for_turnover(conn, turnover_id, unit_row,
> property_id). Load active task templates for the unit\'s phase. Apply
> filters (has_carpet, has_wd_expected). Create one task per template.
> Reference Blueprint Section 4.3.

Step 5.6 --- Import Orchestrator

**PROMPT:**

> Implement services/imports/orchestrator.py. Function:
> import_report_file(conn, file, report_type, property_id). Pipeline:
> validate file, validate schema, parse rows, create import_batch,
> dispatch to report-specific module, run post-processing, return
> structured result with counts and diagnostics. Reference Architecture
> Rules Section 4.1.

**✅ CHECKPOINT: All four report types import correctly. MOVE_OUTS
creates turnovers. Other reports update only. Every row produces a
validation outcome. Manual overrides are respected. Auto-cancel works
after 2 missed MOVE_OUTS batches. Diagnostics are recorded.**

Phase 6 --- Board and Query Layer

Build the read-optimized query service and caching layer that powers all
UI screens.

Step 6.1 --- Board Query Service

**PROMPT:**

> Implement services/board_query_service.py. Function:
> get_dmrb_board_rows(conn, property_id, phase_ids, today). Pipeline:
> query open turnovers, batch-load units/tasks/notes/risks for those
> turnovers, call domain/enrichment.enrich_row for each turnover, return
> list of enriched row dicts. Also implement get_flag_bridge_rows,
> get_risk_radar_rows, get_turnover_detail. Enrichment must happen in a
> single pass over pre-fetched data (no per-row DB calls). Reference
> System Map Section 14.1.

Step 6.2 --- Report Operations Service

**PROMPT:**

> Implement services/report_operations_service.py. Functions:
> get_missing_move_out_queue (import rows indicating move-in without
> turnover), get_fas_tracker_rows, get_import_diagnostics_queue (non-OK
> import rows), resolve_missing_move_out (create turnover via
> manual_availability_service), upsert_fas_note. Reference System Map
> Section 6.

Step 6.3 --- Cache Layer

**PROMPT:**

> Implement ui/data/cache.py. Use st.cache_data with TTL (5-10 seconds)
> for board queries, property/phase/building/unit lists. Implement
> invalidate_board_caches() and invalidate_ui_caches() functions. Cache
> keys must include property_id and today\'s date. Follow the cache
> invalidation contract from Architecture Rules Section 5.3.

Step 6.4 --- Backend Bootstrap

**PROMPT:**

> Implement ui/data/backend.py. Backend availability check and
> bootstrap: call ensure_database_ready(), run reconcile_missing_tasks()
> once per process. Expose get_conn() for UI layer. Set
> BACKEND_AVAILABLE flag. Reference System Map Section 9.

**✅ CHECKPOINT: Board query returns enriched rows for all open
turnovers. Enrichment produces correct DV, DTBR, NVM, risk scores, and
attention badges. Cache layer works with TTL and invalidation. Report
operations queries return correct diagnostic data.**

Phase 7 --- UI Screens

Rebuild the Streamlit interface. Screens are thin presentation layers.
Build one screen at a time.

Step 7.1 --- Auth, Router, Sidebar, Session

**PROMPT:**

> Implement: ui/auth.py (simple login gate checking credentials from
> config/settings), ui/router.py (read session_state.page, lazy-import
> screen module, call render()), ui/components/sidebar.py (navigation
> with page selection), ui/state/session.py (initialize all session
> state defaults). Reference System Map Section 9.

Step 7.2 --- Board Screen

**PROMPT:**

> Implement ui/screens/board.py. This is the main operational screen. It
> must: load enriched rows from cached board query, display filters
> (phase, status, NVM, assignee, search), display the turnover grid with
> Unit Info and Unit Tasks tabs, support inline editing of status,
> dates, and task statuses via st.data_editor, route edits through
> application workflows, invalidate caches after writes. Keep under 200
> lines by extracting table rendering into ui/components/tables.py and
> filters into ui/components/filters.py. Reference Blueprint Section 9
> for the operational workflow this screen supports.

Step 7.3 --- Turnover Detail Screen

**PROMPT:**

> Implement ui/screens/turnover_detail.py. Single turnover deep view
> with panels: unit info, status and QC, dates with override controls,
> W/D state, risks, authority and import comparison, tasks with per-task
> editing, notes. All edits go through application workflows. Reference
> System Map Section 13 for services used.

Step 7.4 --- Supporting Screens

**PROMPT:**

> Implement the remaining screens one at a time:
> ui/screens/morning_workflow.py (daily checklist: import freshness,
> missing move-out queue, priority units), ui/screens/flag_bridge.py
> (flag-focused filtered view, read-only), ui/screens/risk_radar.py
> (risk-scored ranked view, read-only), ui/screens/report_operations.py
> (missing move-out queue, FAS tracker, import diagnostics tabs),
> ui/screens/admin.py (property management, import console, unit master,
> task template config, exports). Each screen under 200 lines. Each
> screen calls services only. Reference System Map Section 9 for each
> screen\'s responsibility.

Step 7.5 --- Export Screen

**PROMPT:**

> Implement ui/screens/exports.py and services/export_service.py.
> Generate Excel reports and summaries from enriched board data. Provide
> download buttons. Reference System Map Sections 6 and 9.

**✅ CHECKPOINT: All screens render and navigate correctly. Board loads
enriched data and supports inline editing. Turnover detail shows full
turnover state. Imports work from Admin. Diagnostics display in Report
Operations. Auth gate works. All screens under 200 lines.**

Phase 8 --- Verification and Hardening

Add tests, logging, performance tuning, and deployment preparation.

Step 8.1 --- Domain Tests

**PROMPT:**

> Write tests for all domain modules: test_lifecycle.py (all phase
> derivations, NVM labels, effective move-out precedence),
> test_enrichment.py (DV, DTBR, task completion, operational states),
> test_risk_engine.py (all risk types and trigger conditions),
> test_sla_engine.py (breach detection, stop dominance, edge cases).
> Pure unit tests, no database. Reference Architecture Rules Section 8.

Step 8.2 --- Service and Import Tests

**PROMPT:**

> Write tests for critical service invariants: one open turnover per
> unit (rejection of duplicates), task transition validation, import
> scenarios (OK, CONFLICT, IGNORED, SKIPPED_OVERRIDE for each report
> type), auto-cancel after 2 missed MOVE_OUTS. Use a test database or
> SQLite. Include sample CSV fixtures in tests/fixtures/. Reference
> Architecture Rules Section 8.

Step 8.3 --- Structured Logging

**PROMPT:**

> Add structured logging to services: import batch summaries (rows
> processed, OK/conflict/invalid counts), turnover lifecycle
> transitions, SLA breach events, error conditions with context. Use
> Python logging module. No print statements. Reference Architecture
> Rules Section 10.

Step 8.4 --- Performance Review

**PROMPT:**

> Review board load performance for 200 turnovers. Check: number of DB
> queries per board load, enrichment computation time, cache hit rates.
> Ensure board loads in under 2 seconds. Add database indexes if needed.
> Verify no N+1 query patterns. Reference Architecture Rules Sections
> 3.3 and the Blueprint board speed target of 1-2 seconds.

Step 8.5 --- Deployment Preparation

**PROMPT:**

> Prepare for Streamlit Community Cloud deployment. Verify:
> requirements.txt is complete, .streamlit/secrets.toml has the correct
> structure for Supabase connection, config/settings.py resolves secrets
> correctly, ensure_database_ready() runs cleanly on first deploy, auth
> gate works with environment credentials. Create a deployment
> checklist.

**✅ CHECKPOINT: Domain tests pass. Critical service invariants are
tested. Import scenarios produce expected outcomes. Board loads in under
2 seconds for 200 turnovers. App deploys to Streamlit Cloud and connects
to Supabase. Auth works. System is production-ready.**

Execution Sequence Summary

Follow this exact order. Do not skip phases. Complete each checkpoint
before proceeding.

  ---------- ------------------------------------------ ----------------------
  **Step**   **Action**                                 **Checkpoint**

  1.1        Create folder structure                    All folders match
                                                        System Map

  1.2        Create requirements.txt                    Dependencies listed

  1.3        Create config/settings.py                  Environment-first
                                                        resolution works

  1.4        Create app.py shell                        Under 50 lines, no
                                                        business logic

  2.1        Design core schema                         All tables,
                                                        constraints,
                                                        invariants enforced

  2.2        Create connection module                   Supabase-compatible
                                                        connection works

  2.3        Create initial migration                   Migration applies
                                                        cleanly

  2.4        Create repository shells                   All entity repos exist
                                                        with placeholders

  3.1        Unit identity domain                       Normalization and
                                                        parsing work

  3.2        Lifecycle domain                           All phases derive
                                                        correctly

  3.3        Enrichment domain                          All board fields
                                                        compute correctly

  3.4        Risk engine domain                         All risk types
                                                        evaluate correctly

  3.5        SLA engine domain                          Breach and stop
                                                        dominance work

  3.6        Risk radar domain                          Score and level
                                                        compute correctly

  4.1        Repository implementation                  All CRUD operations
                                                        work

  4.2        Property and unit services                 Structural services
                                                        work

  4.3        Turnover service                           Create, update, close,
                                                        reconcile all work

  4.4        Task service                               Status transitions and
                                                        audit work

  4.5        Risk and SLA services                      Reconciliation works
                                                        correctly

  4.6        Note service                               Create and resolve
                                                        work

  4.7        Application workflows                      Commands route to
                                                        services correctly

  5.1        Import validation                          File and schema
                                                        validation work

  5.2        Import common helpers                      Unit resolution and
                                                        diagnostics work

  5.3        MOVE_OUTS importer                         Creates turnovers,
                                                        handles overrides,
                                                        auto-cancel works

  5.4        Other importers                            MOVE_INS,
                                                        AVAILABLE_UNITS,
                                                        PENDING_FAS all work

  5.5        Task instantiation                         Templates create
                                                        correct tasks

  5.6        Import orchestrator                        Full pipeline
                                                        dispatches correctly

  6.1        Board query service                        Enriched rows return
                                                        correctly

  6.2        Report operations service                  Diagnostic queries
                                                        work

  6.3        Cache layer                                TTL and invalidation
                                                        work

  6.4        Backend bootstrap                          DB ready, missing
                                                        tasks reconciled

  7.1        Auth, router, sidebar                      Navigation and login
                                                        work

  7.2        Board screen                               Main board renders and
                                                        edits work

  7.3        Turnover detail                            Full detail view and
                                                        editing work

  7.4        Supporting screens                         All secondary screens
                                                        render

  7.5        Export screen                              Report generation
                                                        works

  8.1        Domain tests                               All domain tests pass

  8.2        Service and import tests                   Invariant tests pass

  8.3        Structured logging                         Services produce
                                                        useful logs

  8.4        Performance review                         Board loads in \< 2
                                                        seconds

  8.5        Deployment preparation                     App deploys to
                                                        Streamlit Cloud
  ---------- ------------------------------------------ ----------------------

*End of Rebuild Roadmap*
