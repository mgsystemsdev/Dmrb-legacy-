# Export Report Build Guide

Status note: This is a target-state build guide, not a description of the current running system. The current implementation only has placeholder export UI. For current-state truth, see `export_architecture_blueprint.md`.

## Purpose

This document explains the full export system: what each report is for, what data it depends on, how each file is constructed, and how the legacy implementation maps to the rebuild.

The key architectural rule is simple:

`board/enrichment data -> export preparation -> report builders -> downloadable files`

Exports are not a separate business logic system. They are renderers over the same enriched turnover dataset that powers the board.

## Export Inventory

The export system produces five outputs:

- `Final_Report.xlsx`
- `DMRB_Report.xlsx`
- `Dashboard_Chart.png`
- `Weekly_Summary.txt`
- `DMRB_Reports.zip`

## System Model

### What exports consume

Every export starts from the same enriched turnover list. In legacy, this was `buildEnrichedTurnovers()`. In the rebuild, the equivalent should be a dedicated export-prep layer built on top of the board service.

The dataset must contain:

- raw turnover fields
- unit identity fields
- task list
- note list
- risk flag list
- computed lifecycle, readiness, SLA, and priority fields

### What exports are allowed to do

Export builders may:

- filter rows
- group rows
- bucket values
- aggregate counts and averages
- apply formatting

Export builders must not:

- reimplement lifecycle logic
- reimplement SLA logic
- reimplement readiness or priority logic
- query the database independently per report

## Foundation Layer

Before any report can be built, three layers must exist:

- enriched turnover data
- Excel rendering pipeline
- shared helper functions

## 1. Enriched Turnover Data

### Canonical flow

Legacy flow:

1. Query all open turnovers:
   `SELECT * FROM turnovers WHERE closed_at IS NULL AND canceled_at IS NULL`
2. Query all units and map by `unit_id`.
3. Query tasks, notes, and risk flags for all turnover IDs.
4. Group each related record set by `turnover_id`.
5. Enrich each turnover into a single export row.
6. Return `EnrichedTurnover[]`.

### Required enrichment outputs

Each enriched turnover should contain:

- raw turnover
- unit
- `tasks_list`
- `notes_list`
- `risks_list`
- `dv`
- `dtbr`
- `days_to_move_in`
- `lifecycle_phase`
- `nvm`
- `operational_state`
- `attention_badge`
- `task_completion_ratio`
- `current_task`
- `next_task`
- `is_task_stalled`
- `qc_status`
- `wd_summary`
- `sla_breach`
- `inspection_sla_breach`
- `plan_breach`
- `sla_movein_breach`
- `is_unit_ready`
- `has_violation`

### Field derivation rules

- `dv`: business days between effective move-out and today
- `dtbr`: business days between today and report ready date
- `days_to_move_in`: business days between today and move-in date
- `task_completion_ratio`: `(completed executable tasks / executable tasks) * 100`
- `current_task` / `next_task`: first and second incomplete task in sort order
- `is_task_stalled`: incomplete tasks exist, nothing is in progress, and completion ratio is above zero
- `qc_status`: derived from Final Walk task confirmation status in legacy
- `wd_summary`: derived from washer/dryer presence, install, and supervisor notification flags
- `is_unit_ready`: all tasks complete or unit explicitly confirmed ready
- `has_violation`: true if any breach flag is true

### Rebuild guidance

In the rebuild, this should come from a single export-prep function layered on top of the board service, not from separate report-specific queries.

Recommended shape:

- `services/board_service.py` or equivalent produces board-enriched rows
- `services/export_service.py` normalizes them into export rows
- all report builders consume the same export row list

### Scope rule

Legacy exports ignored UI filters and exported all open turnovers.

For the rebuild, the safest rule is:

- exports follow the active property scope
- exports ignore transient UI filters like search, badge filters, table filters, or drill-down state
- within scope, exports include all open turnovers

## 2. Excel Rendering Pipeline

### Legacy pipeline

The legacy system used a two-stage Excel pipeline because `ExcelJS addTable()` was removed in `v4.4.0`.

Stage 1:

- TypeScript builds a JSON workbook spec

Stage 2:

- Python `openpyxl` reads the spec and writes the `.xlsx`

Stage 3:

- TypeScript writes temp files, calls Python, reads the generated workbook into a buffer, and cleans up temp files

### Workbook spec contract

```ts
interface WorkbookSpec {
  sheets: SheetSpec[];
}

interface SheetSpec {
  name: string;
  tables: TableSpec[];
  conditionalCells: ConditionalCell[];
  sectionTitles: SectionTitle[];
  freeformCells: FreeformCell[];
  columnWidths: ColumnWidth[];
}

interface TableSpec {
  headers: string[];
  rows: (string | number | null)[][];
  startRow: number;
  dateColumns?: number[];
  numberColumns?: number[];
}

interface ConditionalCell {
  row: number;
  col: number;
  fill: string;
}

interface SectionTitle {
  row: number;
  title: string;
  colspan: number;
}

interface FreeformCell {
  row: number;
  col: number;
  value: string | number;
  font?: object;
  fill?: string;
  alignment?: object;
}

interface ColumnWidth {
  col: number;
  width: number;
}
```

### Python writer behavior

The Python writer should:

1. read the JSON input spec
2. create a workbook and remove the default sheet
3. create worksheets in order
4. write section titles
5. write freeform cells
6. apply manual column widths
7. write tables
8. apply number and date formatting
9. auto-size columns
10. apply conditional fills last
11. save to the output path

### Formatting constants

- table style: `TableStyleMedium15`
- date format: `MM/DD/YY`
- number format: `#,##0`
- section title: bold 13pt, color `#1F4E79`
- fill colors:
  - green: `#E2EFDA`
  - amber: `#FFF3E0`
  - red: `#FCE4EC`
  - blue: `#E3F2FD`
  - gray: `#F5F5F5`
  - yellow: `#FFF9C4`
  - header_blue: `#4472C4`
- column width auto-size: `max(content + 2, 10)` capped at `40`

### Rebuild guidance

The rebuild is Python-first, so it does not need the TypeScript-to-Python bridge. The cleanest rebuild is:

- Python export service
- Python workbook writer using `openpyxl`
- in-memory bytes returned directly to the UI

The legacy spec is still useful as a construction model, even if the rebuild does not literally use TypeScript.

## 3. Shared Helper Functions

### Fill-name helpers

- `statusFillName(status)`
  - green for `vacant ready` or `ready`
  - red for `not ready`
  - gray for `notice`
- `alertFillName(badge)`
  - red for `CRITICAL` or `STALLED`
  - green for `READY` or `APARTMENT READY`
  - amber for `NEEDS ATTENTION`
  - blue for `IN PROGRESS`
  - gray for `NOTICE` or `CANCELED`
- `dvFillName(dv)`
  - green if `<= 5`
  - amber if `6-20`
  - red if `> 20`
- `progressFillName(pct)`
  - green if `>= 75`
  - amber if `25-74`
  - red if `< 25`
- `taskStatusFillName(status)`
  - green for `COMPLETED` or `NA`
  - blue for `IN_PROGRESS` or `SCHEDULED`
  - red for `NOT_STARTED`
- `wdFillName(wd)`
  - green for `OK` or `INSTALLED`
  - amber for `NOTIFIED` or `ORDERED`
  - red for `PENDING` or `MISSING`

### Sheet helpers

- `createSheet(name)`
- `addTable(sheet, headers, rows, options)`
- `addSection(sheet, row, title, colspan)`

`addTable()` should gracefully handle empty datasets by writing header cells as freeform cells rather than creating an invalid Excel table.

## Report 1: Final Report

### Purpose

The Final Report is a reconciliation workbook. It reorganizes the same turnover dataset into seven operational views without adding new business logic.

### Output

`Final_Report.xlsx`

### Sheets

#### 1. Reconciliation

Headers:

- Phase
- Unit
- Status
- Available Date
- Move-In Ready Date
- Move In Date
- MO/Confirm

Filter:

- all turnovers

Row mapping:

- Phase: legacy used `t.unit.building`; rebuild should use the correct phase/building display consistently
- Unit: unit code
- Status: manual ready status or equivalent display status
- Available Date: confirmed move-out date or move-out date
- Move-In Ready Date: report ready date
- Move In Date: move-in date
- MO/Confirm: `Yes` if confirmed move-out exists

Formatting:

- date columns: 4, 5, 6
- status fill on column 3
- green fill on column 7 when value is `Yes`

#### 2. Split View

Same headers as Reconciliation.

Two sections:

- `Has Move In`
- `No Move In`

Rows are split by whether a move-in date exists. Each section gets its own title and table. Conditional cell coordinates must respect each table’s actual starting row.

#### 3. Available Units

Headers:

- Phase
- Unit
- Status
- Available Date
- Move-In Ready Date

Filter:

- `lifecycle_phase === 'VACANT'`

Formatting:

- date columns: 4, 5
- status fill on column 3

#### 4. Move Ins

Headers:

- Phase
- Unit
- Move In Date

Filter:

- turnovers with a move-in date

Formatting:

- date column: 3

#### 5. Move Outs

Headers:

- Phase
- Unit
- Move-Out Date

Filter:

- all turnovers

Formatting:

- date column: 3

#### 6. Pending FAS

Headers:

- Phase
- Unit
- MO/Cancel Date
- Lease End
- Completed

Filter:

- `lifecycle_phase === 'NOTICE'`

Notes:

- `Completed` is an empty placeholder column in legacy

Formatting:

- date columns: 3, 4

#### 7. Move Activity

Headers:

- Phase
- Unit
- Move-Out Date
- Move In Date

Filter:

- all turnovers

Formatting:

- date columns: 3, 4

### Build rule

Build one workbook spec or workbook object, add the seven sheets in order, and return workbook bytes.

## Report 2: DMRB Report

### Purpose

The DMRB Report is the detailed operational workbook. It is the most complex export and contains a mix of tables, freeform bucket grids, and aggregated sheets.

### Output

`DMRB_Report.xlsx`

### Sheets

#### 1. Dashboard

Headers:

- Phase
- Unit
- Status
- Days Vacant
- M-I Date
- Alert

Filter:

- all turnovers

Formatting:

- date column: 5
- status fill on column 3
- DV fill on column 4
- alert fill on column 6

#### 2. Aging

This sheet uses a freeform bucket grid, not a normal table.

Buckets:

- `1-10`
- `11-20`
- `21-30`
- `31-60`
- `61-120`
- `120+`

Sections:

- Aging Buckets — All Units
- Aging Buckets — Vacant Ready
- Aging Buckets — Vacant Not Ready

Cell text format:

- `Unit {unit_code} ({status}) | DV-{dv}`

Fill behavior:

- green for ready
- red for not ready

Column widths:

- set all bucket columns to `45`

#### 3. Active Aging

This is a dynamic bucket grid by phase/building.

Filter:

- vacant not-ready units with `dv > 0`

Rules:

- build 10-day buckets dynamically up to max DV
- only include buckets that actually have data
- group by building or phase display
- every non-empty cell gets red fill

#### 4. Operations

This is a multi-section sheet with independent section tables.

Sections:

- Move-In Dashboard
- SLA Breach
- Inspection SLA
- Plan Breach
- Task Stalled
- Clean Turn

Rules:

- each section gets a title
- each section writes a table or an italic gray `No data` message
- add a 2-row gap after each section

#### 5. Walking Path Board

Headers:

- Phase
- Building
- Unit
- Status
- Move In
- Alert
- Insp
- Paint
- MR
- HK
- CC
- QC
- Notes

Filter:

- all turnovers

Formatting:

- status fill on column 4
- alert fill on column 6
- task status fill on columns 7 through 12

Important legacy detail:

- `QC` is derived from Final Walk confirmation, not the QC task

Rebuild note:

- confirm whether that behavior should remain or whether QC should come from the rebuild’s dedicated QC task

#### 6. Tasks

Headers:

- Phase
- Unit
- Current Task
- Task Date
- Next
- Next Date
- Progress %

Rules:

- task dates come from the matching current and next task records
- use a task-label-to-task-key mapping
- apply progress fill on column 7

#### 7. Schedule

Five sections, one per task type:

- Inspection
- Paint
- Make Ready
- Housekeeping
- Carpet Clean

Rules:

- each section title spans 3 columns
- rows come from tasks with `scheduled_date`
- empty sections show `No scheduled items`

#### 8. Upcoming

Same structure as Schedule, but rows come from tasks whose `vendor_due_date` falls within the next 7 days.

Empty message:

- `No upcoming items`

#### 9. WD Audit

Headers:

- Phase
- Unit
- W/D

Formatting:

- apply W/D fill on column 3

#### 10. Daily Ops

This sheet is two key-value sections.

Section 1: Portfolio Overview

- Total Units
- Vacant
- On Notice

Section 2: Turn Performance

- Avg Days Vacant
- Avg Completion %
- SLA Breaches
- Plan Breaches
- Ready Units

#### 11. Priority

Headers:

- Phase
- Unit
- Priority_Flag
- Urgency_Reason

Legacy urgency reason logic:

- `Move-In Risk` if `sla_movein_breach`
- `SLA Breach` if `sla_breach`
- `Plan Breach` if `plan_breach`

Formatting:

- alert fill on column 3
- yellow fill on column 4 when non-empty

#### 12. Phase Performance

Headers:

- Phase
- Count
- Avg DV
- SLA Compliance %
- Completion Rate

Aggregation:

- group by building or phase display
- count units
- mean DV
- percent non-breach
- mean task completion ratio

Formatting:

- green if SLA compliance `>= 90`
- yellow if `>= 70`
- red otherwise

### Build rule

Build the workbook in order and return workbook bytes.

## Report 3: Dashboard Chart

### Purpose

This is a visual portfolio snapshot: one PNG with nine bar charts in a 3×3 layout.

### Output

`Dashboard_Chart.png`

### Legacy implementation

Legacy used:

- `chartjs-node-canvas`
- `canvas`
- `chart.js`

with a `1600x1200` master canvas and `500x350` child chart renderings.

### Chart inventory

#### 1. Turn Time Distribution

- labels: `0-5`, `6-10`, `11-15`, `16-20`, `21+`
- values: count by DV bucket
- color: `#3b82f6`

#### 2. Units by State

- labels: unique `operational_state`
- values: count per state
- color: `#10b981`

#### 3. Task Completion

- labels: `0-25%`, `26-50%`, `51-75%`, `76-100%`
- values: count by completion bucket
- color: `#f59e0b`

#### 4. SLA by Phase

- labels: unique phase/building values
- values: count of `sla_breach === true`
- color: `#ef4444`

#### 5. Avg Turn Time by Phase

- labels: unique phase/building values
- values: average DV per group
- color: `#8b5cf6`

#### 6. Task Completion Rate

- labels: unique phase/building values
- values: average completion ratio per group
- color: `#ec4899`

#### 7. Vacancy Rate by Phase

- labels: unique phase/building values
- values: count where `lifecycle_phase === 'VACANT'`
- color: `#6366f1`

#### 8. Units by Badge

- labels: unique `attention_badge`
- values: count per badge
- color: `#14b8a6`

#### 9. Days Until Move-In

- labels: `0-2`, `3-7`, `8-14`, `15+`
- values: count by `days_to_move_in` bucket
- color: `#f97316`

### Rebuild guidance

The rebuild can stay Python-native here as well. A `matplotlib` `Agg` implementation is simpler than reproducing the Node chart stack unless exact visual parity is required.

## Report 4: Weekly Summary

### Purpose

This is a plain-text operational digest built with string concatenation.

### Output

`Weekly_Summary.txt`

### Sections

#### 1. Key Metrics

- Total Active
- Vacant
- On Notice
- SLA Compliance %
- Ready Units
- Avg Days Vacant

#### 2. Alerts

- SLA Breaches
- Move-In Risk
- Stalled Tasks
- Plan Breaches

Each alert section should include the affected unit list and any relevant context like due dates or current task.

#### 3. Upcoming Move-Ins

- rows with move-in date in the next 7 days

#### 4. Upcoming Ready

- rows with ready date in the next 7 days

#### 5. W/D Not Installed

- rows where washer/dryer is present but not installed

#### 6. Aging Distribution

- counts for:
  - `1-10`
  - `11-20`
  - `21-30`
  - `31-60`
  - `61-120`
  - `120+`

### Build rule

Compute metrics and lists from the turnover array, format the text, and return UTF-8 bytes or a string depending on the caller contract.

## Report 5: All Reports ZIP

### Purpose

This is the bundle export.

### Output

`DMRB_Reports.zip`

### Build steps

1. build enriched turnovers once
2. generate Final Report
3. generate DMRB Report
4. generate Dashboard Chart
5. generate Weekly Summary
6. package all four outputs into one ZIP

### Legacy packaging

Legacy used `archiver` with `zlib level 9` and streamed the ZIP directly to the HTTP response.

### Rebuild guidance

In the rebuild, the same packaging can be done in memory with Python’s `zipfile` module if the UI is Streamlit-based.

## API / Delivery Wiring

### Legacy route model

Legacy exposed one GET route per export:

- `/api/export/final-report`
- `/api/export/dmrb-report`
- `/api/export/dashboard-chart`
- `/api/export/weekly-summary`
- `/api/export/all`

Each route:

1. built enriched turnovers
2. generated the target artifact
3. set `Content-Type`
4. set `Content-Disposition`
5. returned bytes or streamed ZIP output

### Rebuild UI model

The rebuild already has an Export tab in `ui/screens/admin.py`.

Recommended flow:

1. user clicks `Prepare Export Files`
2. export service builds the turnover list once
3. export service generates all artifacts
4. artifacts are stored in session state or short-lived cache
5. download buttons bind to real file bytes

## Dependencies

### Legacy Node packages

- `chartjs-node-canvas`
- `canvas`
- `chart.js`
- `archiver`

### Python package

- `openpyxl`

### Rebuild likely Python packages

- `openpyxl`
- `matplotlib` if chart generation is moved fully into Python

## Recommended Build Order

1. implement `build_export_turnovers()`
2. implement fill-name helpers and shared export utilities
3. implement Excel writer helpers
4. implement Weekly Summary
5. implement Dashboard Chart
6. implement Final Report
7. implement DMRB Report
8. implement ZIP bundle
9. wire the Admin Export tab to generated bytes

This order validates the shared dataset and formatting layer before the most complex workbook lands.

## Key Rebuild Decisions To Confirm

- should exports remain property-scoped or revert to cross-property scope
- should `Phase` display true phase, building, or both
- should QC status continue to come from Final Walk confirmation or move to the QC task
- should export notes include all notes or only open notes
- should charts remain visually identical to legacy or simply preserve the same metrics

## Bottom Line

The export system is a reporting layer over board truth.

The correct rebuild strategy is:

`board service -> export preparation -> file builders -> Admin downloads`

not:

`raw tables -> report-specific calculations -> downloads`
