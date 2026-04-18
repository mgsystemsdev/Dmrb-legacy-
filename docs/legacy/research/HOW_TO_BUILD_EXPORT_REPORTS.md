# How to Build Each Export Report

This document explains **how to construct** each of the five export outputs (Final Report XLSX, DMRB Report XLSX, Dashboard Chart PNG, Weekly Summary TXT, and All Reports ZIP). It describes the code structure, data flow, and step-by-step build process in natural language so you or another agent can implement or replicate the exports without guessing.

---

## 1. Shared Foundation: Data and Helpers

Before building any single report, you need one shared data pipeline and a small set of helpers.

### 1.1 How to Get the Export Data

**Step 1 — Load board rows.** Call your board query service with a database connection and today’s date. The service must return a list of flat dictionaries, one per **open** turnover (closed and canceled excluded). Do **not** apply UI filters (property, phase, status, etc.); exports use **all** open turnovers. Each row must already include:

- Turnover fields: `turnover_id`, `move_out_date`, `move_in_date`, `report_ready_date`, `manual_ready_status`, `confirmed_move_out_date`, `scheduled_move_out_date`, `wd_present`, `wd_installed`, `wd_supervisor_notified`, and any other turnover columns you use.
- Unit identity: `unit_code`, `building` (or equivalent for “phase” display), and whatever you use for phase/building/unit.
- Per-task objects: `task_insp`, `task_paint`, `task_mr`, `task_hk`, `task_cc`, `task_cb`, `task_mrb`, `task_fw`, `task_qc`, each with at least `execution_status`, `confirmation_status`, `vendor_due_date`, `scheduled_date`.
- Enrichment fields: `dv`, `dtbr`, `nvm`, `phase`, `operational_state`, `attention_badge`, `sla_breach`, `plan_breach`, `inspection_sla_breach`, `is_task_stalled`, `task_completion_ratio`, `current_task`, `next_task`, `days_to_move_in`, `is_unit_ready`, and any other computed fields your board uses.

**Step 2 — Build export-specific fields.** For each row, add:

- **QC status:** From the **Final Walk** task (`task_fw`), not the QC task. Read `confirmation_status`: CONFIRMED → "Confirmed", REJECTED → "Rejected", else "Pending". If there is no Final Walk task, use "N/A".
- **W/D summary:** If the unit has no washer/dryer (`wd_present` false), use "—". If `wd_installed` is true, use "OK". If `wd_supervisor_notified` is true but not installed, use "NOTIFIED". Otherwise use "PENDING".
- **Notes (joined):** Fetch **all** notes for the turnover (not only unresolved). Join their text with a separator (e.g. "; ") and store in a field like `notes_joined`. If the board only loads unresolved notes, you must do a separate query here with unresolved_only=false.
- **Available date:** Use `confirmed_move_out_date` if present, else `move_out_date`.
- **Days to move-in:** If not already set by enrichment, compute (move_in_date − today).days when move_in_date exists; otherwise leave null.

**Step 3 — Sort.** The list is typically sorted by: (1) rows with a move-in date first, then rows without; (2) by move-in date ascending; (3) by days vacant (DV) descending within groups. Your board query may already return this order; if not, sort the list once before passing it to any report builder.

**Result:** A single function, e.g. `build_export_turnovers(conn, today)`, that returns this list of enriched dictionaries. Every report then receives the **same** list; no report hits the database directly.

### 1.2 Helper Functions You Need

Implement these in one place (e.g. export service or shared util) and reuse:

- **Phase display:** Given a row, return the string to show as "Phase" (e.g. `row["building"]` or a combination of phase/building). Use it consistently so "Phase" means the same in every sheet and report.
- **Unit display:** Return the unit identifier string (e.g. `row["unit_code"]`).
- **Status label:** Return the human-readable status (e.g. `manual_ready_status`: "Vacant ready", "Vacant not ready", "On notice").
- **Date parsing:** A function that accepts a value (string, date, or datetime) and returns a date or None; use it for all date columns so formatting is consistent.
- **Row classifiers:**  
  - **Has move-in:** True if move_in_date parses to a non-null date.  
  - **Is vacant:** True if the row is considered vacant (e.g. status or nvm indicates "Vacant").  
  - **Is on notice:** True if the row is on notice (e.g. "Notice" in status or nvm).  
  - **Status is ready / not ready:** Based on the status label (e.g. "ready" in label and "not ready" not in label → ready).
- **Safe numeric:** Safe int and float helpers that return a default (e.g. 0) when the value is missing or not a number.
- **DV bucket label:** Map days vacant (int) to bucket strings: 1–10 → "1-10", 11–20 → "11-20", 21–30 → "21-30", 31–60 → "31-60", 61–120 → "61-120", else "120+".

You will use these in filtering, grouping, and cell formatting.

### 1.3 Excel Writing Layer

You need a thin wrapper around openpyxl so that every report uses the same look:

- **Create workbook / new sheet:** Create a workbook and add sheets by name; reuse the first sheet for the first tab instead of leaving a default empty sheet.
- **Write section title:** Merge cells across the given number of columns, set bold blue font, write the title (e.g. "Has Move In", "Aging Buckets — All Units").
- **Write table:** Write a header row (bold), then data rows. For each cell, set center/wrap alignment; for date values use a consistent date format (e.g. MM/DD/YY); for numbers use a number format. Optionally register the range as an Excel table with a table style (e.g. TableStyleMedium15) so columns and stripes look consistent.
- **Write empty state:** When a section has no rows, write the header row and then a single merged row with an italic message like "No data" or "No scheduled items".
- **Apply fill:** Given a sheet, row index, column index, and a fill name (e.g. "green", "red", "amber"), set the cell’s fill to the corresponding color. Define a small palette (green, amber, red, blue, gray, yellow, header_blue) and map status/alert/DV/completion/WD/SLA to fill names (see below).
- **Auto-size columns:** After writing a sheet, set each column width from content (with min and max width) so the file is readable.
- **Workbook to bytes:** Save the workbook to an in-memory buffer and return the bytes (for download or zipping).

Define fill-name helpers that take a value and return a fill name:

- **Status fill:** "Vacant not ready" / "not ready" → red; "Vacant ready" / "ready" → green; "On notice" / "notice" → gray.
- **Alert fill:** Map attention_badge (or similar) to red / green / amber / blue / gray by keyword (e.g. CRITICAL, STALLED → red; READY, SCHEDULED → green).
- **DV fill:** Days vacant ≤ 5 → green; ≤ 20 → amber; else red.
- **Progress fill:** Task completion ratio ≥ 75% → green; ≥ 25% → amber; else red.
- **Task status fill:** Map execution status (e.g. Done, In Progress, Not Started) to green / blue / red.
- **W/D fill:** OK/Installed → green; Notified → amber; Pending → red.
- **SLA compliance fill:** Percentage ≥ 90 → green; ≥ 70 → yellow; else red.

Use these everywhere you need conditional formatting so the reports look consistent.

---

## 2. How to Build the Final Report (XLSX)

The Final Report is one workbook with **seven sheets**. Every sheet uses the same phase/unit display and date parsing; only the set of rows and columns change.

### 2.1 Row Builder

Define a single function that, given one turnover row, returns a list of cell values for the **main** columns: Phase, Unit, Status, Available Date, Move-In Ready Date, Move In Date, MO/Confirm. Phase and Unit come from the helpers; Status from the status label; Available Date = parsed `available_date`; Move-In Ready Date = parsed `report_ready_date`; Move In Date = parsed `move_in_date`; MO/Confirm = "Yes" if `confirmed_move_out_date` is set, else empty string. Use the date parser for every date so they display consistently.

### 2.2 Sheet 1 — Reconciliation

- Create a sheet named "Reconciliation".
- Write the header row: Phase, Unit, Status, Available Date, Move-In Ready Date, Move In Date, MO/Confirm.
- For **every** turnover in the list, add one data row using the row builder.
- After writing the table, loop over data rows and: (1) apply the status fill to the Status column (column 3); (2) if the row has `confirmed_move_out_date`, apply green fill to the MO/Confirm column (column 7).
- Auto-size columns.

### 2.3 Sheet 2 — Split View

- Create a sheet named "Split View".
- Split the turnover list into two: rows that have a move-in date, and rows that do not.
- Write a section title "Has Move In" spanning the number of columns (7).
- Write the same header row as Reconciliation, then all data rows for the "has move-in" set. Apply status fill to the Status column and green to MO/Confirm where confirmed.
- Leave a blank row, then write section title "No Move In".
- Write the header row again, then all data rows for the "no move-in" set. Apply the same status and MO/Confirm fills.
- Auto-size columns.

### 2.4 Sheet 3 — Available Units

- Create a sheet "Available Units".
- Filter the list to rows where the row is **vacant** (using your is-vacant helper).
- Headers: Phase, Unit, Status, Available Date, Move-In Ready Date (no Move In Date or MO/Confirm).
- For each vacant row, write Phase, Unit, Status, available date, report_ready date. Apply status fill to the Status column. Auto-size.

### 2.5 Sheet 4 — Move Ins

- Create a sheet "Move Ins".
- Filter to rows that **have a move-in date**.
- Headers: Phase, Unit, Move In Date.
- For each row, write Phase, Unit, parsed move_in_date. No conditional fill. Auto-size.

### 2.6 Sheet 5 — Move Outs

- Create a sheet "Move Outs".
- Use **all** turnovers (no filter).
- Headers: Phase, Unit, Move-Out Date.
- For each row, write Phase, Unit, available_date (parsed). Auto-size.

### 2.7 Sheet 6 — Pending FAS

- Create a sheet "Pending FAS".
- Filter to rows that are **on notice** (using your is-notice helper).
- Headers: Phase, Unit, MO/Cancel Date, Lease End, Completed.
- For each row: Phase, Unit, available_date, scheduled_move_out_date (or equivalent for "lease end"), and empty string for Completed. Auto-size.

### 2.8 Sheet 7 — Move Activity

- Create a sheet "Move Activity".
- Use **all** turnovers.
- Headers: Phase, Unit, Move-Out Date, Move In Date.
- For each row: Phase, Unit, available_date, move_in_date (both parsed). Auto-size.

### 2.9 Return Value

Return the workbook as bytes (e.g. save to BytesIO and getvalue()). The UI will use this for "Download Final Report (XLSX)".

---

## 3. How to Build the DMRB Report (XLSX)

The DMRB Report is one workbook with **twelve sheets**. It uses the same phase/unit/status helpers and the same fill-name helpers; it also needs a **today** date for "upcoming" and for age calculations.

### 3.1 Sheet 1 — Dashboard

- Create sheet "Dashboard".
- Headers: Phase, Unit, Status, Days Vacant, M-I Date, Alert.
- For every turnover, write one row: phase, unit, status label, DV (integer), move_in date (parsed), attention_badge (or empty).
- For each data row: apply status fill to Status column; apply DV fill to Days Vacant column; apply alert fill to Alert column. Auto-size.

### 3.2 Sheet 2 — Aging

- Create sheet "Aging".
- You need a helper that, given a list of rows and optional "force red" flag, writes a **bucket grid**: section title, then a header row with the six DV buckets (1-10, 11-20, 21-30, 31-60, 61-120, 120+). For each row, compute the DV bucket label and append a short line like "Unit X (Status) | DV-N" into the corresponding bucket list. Then write a grid: each column is a bucket, each row is the same row index across buckets (so you may have empty cells). Apply red fill to "not ready" cells (or all cells if force_red); green for "ready". Return the next row index after the grid.
- Build three lists: (1) all units that are vacant or have DV > 0; (2) from that, vacant ready; (3) vacant not ready.
- Call the bucket-grid helper three times: "Aging Buckets — All Units" with list (1); "Aging Buckets — Vacant Ready" with list (2); "Aging Buckets — Vacant Not Ready" with list (3) and force_red=True.
- Set column widths (e.g. 45) for the bucket columns so the text fits.

### 3.3 Sheet 3 — Active Aging

- Create sheet "Active Aging".
- Filter to rows that are **vacant not ready** and have DV > 0. Group these by phase (using phase display).
- For each phase (sorted), write a section title like "Active Aging — {phase} (Vacant Not Ready)". For that phase’s rows, determine which DV buckets appear and write a header row of those bucket labels (in bucket order). Fill a grid: each row’s DV goes into the right bucket; cell text like "Unit X (Status) | DV-N". Apply red fill to every non-empty cell. Then add a blank row and move to the next phase. Set column widths so content is readable.

### 3.4 Sheet 4 — Operations

- Create sheet "Operations".
- Define a list of sections, each with: title, filtered list of rows, column headers, and a function that maps a row to a list of cell values. Sections:  
  - Move-In Dashboard: rows with move-in date; headers Phase, Unit, Days to Move-In; row = phase, unit, days_to_move_in.  
  - SLA Breach: rows where sla_breach is true; headers Phase, Unit; row = phase, unit.  
  - Inspection SLA: rows where inspection_sla_breach is true; same.  
  - Plan Breach: rows where plan_breach is true; same.  
  - Task Stalled: rows where is_task_stalled is true; same.  
  - Clean Turn: rows where task_completion_ratio >= 100; same.
- For each section, write the section title, then either the table (headers + data) or, if the list is empty, the header row plus an empty message like "No data". Auto-size at the end.

### 3.5 Sheet 5 — Walking Path Board

- Create sheet "Walking Path Board".
- Headers: Phase, Building, Unit, Status, Move In, Alert, Insp, Paint, MR, HK, CC, QC, Notes.
- For each turnover, build one row: phase (twice for Phase and Building), unit, status, move_in date, attention_badge, then the execution status of task_insp, task_paint, task_mr, task_hk, task_cc, then qc_status (the one derived from Final Walk), then notes_joined.
- After writing the table, apply status fill to Status; alert fill to Alert; task status fill to Insp, Paint, MR, HK, CC columns. Auto-size.

### 3.6 Sheet 6 — Tasks

- Create sheet "Tasks".
- Headers: Phase, Unit, Current Task, Task Date, Next, Next Date, Progress %.
- For each turnover: phase, unit, current_task, due date of current task (from the task object keyed by current_task label, e.g. "Inspection" → task_insp), next_task, due date of next task, task_completion_ratio (as number).
- You need a small mapping from task label (e.g. "Inspection", "Paint") to the task key (task_insp, task_paint, etc.) and then read vendor_due_date or scheduled_date from that task. Apply progress fill to the Progress % column. Auto-size.

### 3.7 Sheet 7 — Schedule

- Create sheet "Schedule".
- For each of a fixed set of task types (e.g. Inspection, Paint, Make Ready, Housekeeping, Carpet Clean), in order: write a section title with the task name; filter to rows where that task has a **scheduled_date** (parsed to non-null); if any, write table Phase, Unit, Date (scheduled_date); if none, write header and "No scheduled items". Auto-size at the end.

### 3.8 Sheet 8 — Upcoming

- Create sheet "Upcoming".
- Same task types as Schedule. For each: section title; filter to rows where that task’s **vendor_due_date** is within 0–7 days from **today**; if any, write table Phase, Unit, Date (vendor_due_date); if none, write header and "No upcoming items". Auto-size.

### 3.9 Sheet 9 — WD Audit

- Create sheet "WD Audit".
- Headers: Phase, Unit, W/D.
- For each turnover: phase, unit, wd_summary (the derived field: —, PENDING, NOTIFIED, OK). Apply W/D fill to the W/D column. Auto-size.

### 3.10 Sheet 10 — Daily Ops

- Create sheet "Daily Ops".
- Section "Portfolio Overview": two columns (e.g. Metric, Value). Rows: Total Units (len(turnovers)), Vacant (count is_vacant), On Notice (count is_notice).
- Section "Turn Performance": same two columns. Rows: Avg Days Vacant (mean of dv), Avg Completion % (mean of task_completion_ratio), SLA Breaches (count sla_breach), Plan Breaches (count plan_breach), Ready Units (count is_unit_ready). Round numeric values. You can use a simple table write without registering as Excel table if your writer supports it. Auto-size.

### 3.11 Sheet 11 — Priority

- Create sheet "Priority".
- Headers: Phase, Unit, Priority_Flag, Urgency_Reason.
- For each turnover, build Urgency_Reason from: if operational_state is "Move-In Risk" add "Move-In Risk"; if sla_breach add "SLA Breach"; if plan_breach add "Plan Breach"; join with " / ". Row = phase, unit, attention_badge, that string. Apply alert fill to Priority_Flag; if Urgency_Reason is non-empty, apply yellow to that cell. Auto-size.

### 3.12 Sheet 12 — Phase Performance

- Create sheet "Phase Performance".
- Group turnovers by phase. For each phase (sorted): count, average DV, SLA compliance % (count of non–sla_breach / count * 100), average task_completion_ratio. Headers: Phase, Count, Avg DV, SLA Compliance %, Completion Rate. Write one row per phase. Apply SLA compliance fill to the SLA Compliance % column. Auto-size.

### 3.13 Return Value

Return the workbook as bytes. The UI uses this for "Download DMRB Report (XLSX)".

---

## 4. How to Build the Dashboard Chart (PNG)

The Dashboard Chart is a **single PNG image** with a 3×3 grid of bar charts. Use a headless plotting backend (e.g. matplotlib with "Agg") and no interactive display.

### 4.1 Setup

- Create a figure with a 3×3 grid of axes (e.g. 16×12 inches, 100 dpi).
- Define a small helper: given an axis, title, list of labels, list of values, draw a bar chart (bars for values, labels on x-axis), set the title, and optionally rotate x labels (e.g. 30°) so they don’t overlap.

### 4.2 Charts to Draw

1. **Turn Time Distribution** — X labels: "0-5", "6-10", "11-15", "16-20", "21+". Count turnovers by DV: 0–5, 6–10, 11–15, 16–20, 21+.
2. **Units by State** — X labels: distinct values of operational_state (e.g. "Vacant", "On Notice", "Move-In Risk"). Y: count per state.
3. **Task Completion** — X labels: "0-25%", "26-50%", "51-75%", "76-100%". Bucket task_completion_ratio and count.
4. **SLA by Phase** — Group by phase; X = phase names; Y = count of rows with sla_breach true in that phase.
5. **Avg Turn Time by Phase** — Same phases; Y = mean of DV per phase.
6. **Task Completion Rate by Phase** — Same phases; Y = mean of task_completion_ratio per phase.
7. **Vacancy Rate by Phase** — Same phases; Y = count of vacant rows per phase.
8. **Units by Badge** — X = distinct attention_badge values; Y = count per badge.
9. **Days Until Move-In** — X: "0-2", "3-7", "8-14", "15+". Use days_to_move_in (only rows where it is not null); bucket and count.

### 4.3 Layout and Output

- Call tight_layout so the 3×3 grid doesn’t overlap.
- Save the figure to an in-memory buffer as PNG (e.g. BytesIO), then close the figure to free memory.
- Return the buffer’s bytes. The UI uses this for "Download Dashboard Chart (PNG)".

---

## 5. How to Build the Weekly Summary (TXT)

The Weekly Summary is **plain text** (UTF-8), no Excel, no charts. Build one big string and return it as bytes (encode to utf-8).

### 5.1 Computed Lists and Numbers

- Total = number of turnovers; Vacant = count is_vacant; On Notice = count is_notice.
- SLA compliance % = (total − count of sla_breach) / total * 100 (if total 0, use 100).
- Ready units = count is_unit_ready; Avg DV = mean of dv (rounded to 2 decimals).
- Lists: sla_breaches (rows where sla_breach); plan_breaches (plan_breach); move_in_risk (operational_state == "Move-In Risk"); stalled (is_task_stalled); upcoming_moveins (days_to_move_in in 0–7); upcoming_ready (report_ready_date in 0–7 days from today); wd_not_installed (wd_present and not wd_installed).
- Aging distribution: same six DV buckets as in the DMRB Aging sheet; count how many rows fall in each bucket.

### 5.2 Formatting

- **KEY METRICS:** One line per: Total Active, Vacant, On Notice, SLA Compliance %, Ready Units, Avg Days Vacant.
- **ALERTS:** Section with subsections SLA Breaches, Move-In Risk, Stalled Tasks, Plan Breaches. For each, list unit codes; for move-in risk and upcoming move-ins you can append "(due YYYY-MM-DD)"; for stalled you can append "(current task: X)".
- **UPCOMING MOVE-INS:** List units with move-in in 0–7 days (with due date if you like).
- **UPCOMING READY:** List units whose ready date is 0–7 days from today.
- **W/D NOT INSTALLED:** List units with W/D present but not installed.
- **AGING DISTRIBUTION:** One line per bucket (1-10, 11-20, 21-30, 31-60, 61-120, 120+) with the count.

Use simple newlines and optional blank lines between sections. Return the string encoded as UTF-8 bytes for "Download Weekly Summary (TXT)".

---

## 6. How to Build the All-Reports ZIP

- **Input:** The same list of export turnovers and the same **today** date.
- **Steps:**  
  1. Build the Final Report bytes (no today needed).  
  2. Build the DMRB Report bytes (today needed).  
  3. Build the Dashboard Chart bytes (no today needed).  
  4. Build the Weekly Summary bytes (today needed).  
  You can run these four steps in parallel (e.g. a thread pool with four workers) and wait for all to finish.
- **ZIP:** Create an in-memory ZIP file. Add four entries with fixed names: Final_Report.xlsx, DMRB_Report.xlsx, Dashboard_Chart.png, Weekly_Summary.txt, each with the corresponding bytes. Use DEFLATE compression (e.g. level 9). Return the ZIP bytes.
- The UI uses this for "Download All Reports (ZIP)".

---

## 7. How to Wire the Exports Into the UI

- **Prepare step:** On "Prepare Export Files", get a database connection and call the single entry point that: (1) builds the export turnover list once (conn, today); (2) generates all five artifacts (four files + ZIP). Store the result in session state as a dictionary: filename → bytes (e.g. Final_Report.xlsx → bytes, …, DMRB_Reports.zip → bytes).
- **Download buttons:** After prepare, show two columns of download buttons. Each button uses the correct key (e.g. "Final_Report.xlsx"), gets the bytes from the stored dict, and triggers a download with the correct filename and MIME type (XLSX, PNG, TXT, ZIP). If a key is missing, pass empty bytes so the button doesn’t error.
- **Scope note:** Exports always use **all open turnovers**; they do not respect the current screen filters or active property. If you later need property- or phase-scoped exports, the change should be in the data step (e.g. pass property_ids into the board query or filter the list after loading), not in the report builders themselves.

---

## 8. Summary: Build Order and Dependencies

1. **Data:** Implement board query (open turnovers, flat enriched rows) and `build_export_turnovers` (add qc_status, wd_summary, notes_joined, available_date, days_to_move_in; optional sort).
2. **Helpers:** Phase/unit/status/date/classifiers/safe numeric/DV bucket; fill-name helpers for status, alert, DV, progress, task status, W/D, SLA compliance.
3. **Excel writer:** Workbook/sheet creation, section title, table write, empty header + message, apply fill, auto-size, workbook_to_bytes.
4. **Final Report:** One row builder; seven sheets (Reconciliation, Split View, Available Units, Move Ins, Move Outs, Pending FAS, Move Activity) with filters and status/MO/Confirm fills.
5. **DMRB Report:** Twelve sheets (Dashboard, Aging, Active Aging, Operations, Walking Path Board, Tasks, Schedule, Upcoming, WD Audit, Daily Ops, Priority, Phase Performance) with filters, buckets, and fills; pass today for Upcoming and any date-based logic.
6. **Dashboard Chart:** Matplotlib 3×3, nine bar charts from the same turnover list; save PNG to bytes.
7. **Weekly Summary:** Compute metrics and lists, format one string, return utf-8 bytes.
8. **ZIP:** Run the four builders (optionally in parallel), then zip the four files into one ZIP and return its bytes.
9. **UI:** One "Prepare" that calls the full export pipeline and stores filename → bytes; download buttons that read from that store.

This is the full construction guide for the exports: one shared data pipeline, one Excel and fill layer, then four report builders and a ZIP step, and finally the UI wiring.
