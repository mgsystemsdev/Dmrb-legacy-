# DMRB — Apartment Turn Intelligence Pipeline

A Python data pipeline that transforms a raw Excel-based apartment turn tracker into a fully enriched operational report with task tracking, readiness scoring, and SLA compliance enforcement.

The system reads a named Excel Table object, runs three sequential transformation stages, and writes a single output workbook on each execution.

---

## Architecture

```
raw/DMRB_raw.xlsx          (user-maintained input)
        │
        ▼
┌──────────────────────┐
│   io_excel.py        │   Read named Table from workbook
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  Stage 1 — Facts     │   Normalize dates, parse notes, compute aging,
│  (facts.py)          │   detect task state and stalls
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  Stage 2 — Intel     │   Derive readiness, operational state,
│  (intelligence.py)   │   risk flags, and attention badges
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  Stage 3 — SLA       │   Enforce inspection, turn, and move-in SLAs;
│  (sla.py)            │   detect plan breaches
└──────────┬───────────┘
           ▼
output/DMRB_REPORTS.xlsx   (overwritten each run)
```

Each stage accepts a pandas DataFrame, appends new columns, and never mutates upstream data. The pipeline is orchestrated by `src/run.py`.

---

## Project Structure

```
DMRB/
├── raw/
│   └── DMRB_raw.xlsx            # Source workbook (must contain a named Table)
├── output/
│   └── DMRB_REPORTS.xlsx        # Generated report (overwritten each run)
├── src/
│   ├── run.py                   # Entry point — orchestrates the pipeline
│   ├── io_excel.py              # Excel I/O (read named Table, write output)
│   ├── facts.py                 # Stage 1 — Core facts and task mechanics
│   ├── intelligence.py          # Stage 2 — Operational intelligence
│   └── sla.py                   # Stage 3 — SLA and risk enforcement
├── requirements.txt
└── README.md
```

---

## Stage Details

### Stage 1 — Core Facts (`facts.py`)

Extracts raw signals from the spreadsheet without applying business opinions.

| Output Column | Description |
|---|---|
| `Note_Text`, `Note_Category` | Cleaned notes text and keyword classification (HOLD, ISSUE, REOPEN, DECISION, MAYBE) |
| `Has_Assignment` | Whether a crew/vendor is assigned (excludes "Total" placeholder) |
| `Is_MoveIn_Present` | Move-in date exists |
| `Is_Ready_Declared` | Ready date exists |
| `Is_Vacant`, `Is_SMI`, `Is_On_Notice` | Unit lifecycle flags derived from the N/V/M column |
| `Is_Allowed_Phase` | Unit is in an actionable phase (5, 7, or 8) |
| `Is_QC_Done` | QC column marked "Done" |
| `Aging_Business_Days` | Business days elapsed since move-out |
| `Task_State` | All Tasks Complete / In Progress / Not Started |
| `Task_Completion_Ratio` | Percentage of the 5-task sequence completed |
| `Table_Current_Task`, `Table_Next_Task` | Current and next task in the sequence |
| `Is_Task_Stalled` | A task has exceeded its expected completion window |

**Task sequence:** Inspection → Paint → MR → HK → CC, each with a configured business-day offset for stall detection.

### Stage 2 — Operational Intelligence (`intelligence.py`)

Interprets Stage 1 facts into actionable operational states.

| Output Column | Description |
|---|---|
| `Is_Unit_Ready` | Status is "Vacant Ready" and all tasks are complete |
| `Is_Unit_Ready_For_Moving` | Ready, move-in scheduled, and QC done |
| `In_Turn_Execution` | Vacant but not yet ready |
| `Move_In_Happened` | Move-in date is in the past |
| `Operational_State` | One of: On Notice, On Notice - Scheduled, Out of Scope, Move-In Risk, QC Hold, Work Stalled, In Progress, Apartment Ready, Pending Start |
| `Prevention_Risk_Flag` | Unit is in turn execution with a risk indicator (note flag, missing assignment, or active work) |
| `Attention_Badge` | Human-readable status badge for dashboards and reports |

### Stage 3 — SLA & Risk Enforcement (`sla.py`)

Enforces time-based compliance rules.

| Output Column | Description | Threshold |
|---|---|---|
| `Days_To_MoveIn` | Calendar days until scheduled move-in | — |
| `Inspection_SLA_Breach` | Inspection not done within SLA window | 1 business day |
| `SLA_Breach` | Unit not ready within global turn SLA | 10 business days |
| `SLA_MoveIn_Breach` | Unit not ready with imminent move-in | 2 calendar days |
| `Plan_Breach` | Declared ready date has passed but unit is not ready | — |

---

## Input Requirements

The input workbook (`raw/DMRB_raw.xlsx`) must contain an Excel **named Table object** (Insert → Table in Excel). The I/O layer reads the table by name, not by cell range.

**Required columns** (25 total):

```
Unit, Status, Move_out, Ready_Date, DV, Move_in, DTBR, N/V/M,
Insp, Insp_status, Paint, Paint_status, MR, MR_Status,
HK, HK_Status, CC, CC_status, Assign, W_D, QC, P, B, U, Notes
```

The reader automatically strips whitespace from column headers and performs fuzzy matching on sheet/table names to handle trailing spaces.

---

## Quick Start

**Prerequisites:** Python 3.10+

```bash
# Clone and enter the project
cd DMRB

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Place your workbook at raw/DMRB_raw.xlsx, then run:
python src/run.py
```

Output is written to `output/DMRB_REPORTS.xlsx`.

---

## Configuration

Pipeline constants are defined at the top of each stage module:

| Parameter | File | Default | Purpose |
|---|---|---|---|
| `TASK_SEQUENCE` | `facts.py` | Inspection → Paint → MR → HK → CC | Order of the turn task pipeline |
| `TASK_COLS` | `facts.py` | Per-task date/status columns + day offset | Maps tasks to spreadsheet columns and stall thresholds |
| `ALLOWED_PHASES` | `facts.py` | 5, 7, 8 | Phases considered actionable |
| `INSPECTION_SLA_DAYS` | `sla.py` | 1 | Max business days for inspection completion |
| `TURN_SLA_DAYS` | `sla.py` | 10 | Max business days for full turn completion |
| `MOVE_IN_BUFFER_DAYS` | `sla.py` | 2 | Required buffer before move-in date |
| `SHEET_NAME` | `run.py` | DMRB | Worksheet name in source workbook |
| `TABLE_NAME` | `run.py` | DMRB5 | Named Table within the worksheet |

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| pandas | >= 2.0 | DataFrame operations |
| openpyxl | >= 3.1 | Excel read/write |
| numpy | >= 1.24 | Business day calculations, conditional logic |







Set `OPENAI_API_KEY` via your environment or Streamlit secrets. Do not commit API keys to git.

