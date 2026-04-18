🏢 Apartment Turnover Management System
Master Specification & Operating Contract (v1 — FINAL)
1. Executive Summary
This system manages apartment turnover (make-ready) operations using:
Excel as the primary engine and source of truth
Python as an augmentation layer, never a replacement
A strict separation between:
Operational data & intent (Excel)
Normalization, logic, and intelligence (Python)
Visibility, prioritization, and capacity views (Python outputs)
The system is designed to:
Protect move-ins above all else
Enforce a 10-business-day turn SLA
Encode real operational judgment
Prevent false urgency
Remain stable, deterministic, and extensible
This document defines exactly how the system thinks and serves as the frozen v1 contract.
2. Core Design Principles (Non-Negotiable)
Excel is the engine
All 25 Excel columns remain untouched
Excel remains authoritative for operational facts
Python augments Excel
Python adds normalized, deterministic, and computed intelligence
Python never replaces Excel calculations
Move-ins are the highest priority
If a unit is not ready for move-in, the system has failed
Plans matter more than internal task timing
Ready_Date is the promise to the business
Urgency ≠ Visibility
Some urgent units are intentionally hidden
No silent assumptions
Every rule is explicit and documented
3. System Architecture
3.1 Layered Model
Layer
Responsibility
Excel Table
Facts, dates, statuses, human intent
Python Engine
Normalization, rules, flags, logic
Python Views
Cockpit, planning, escalation
Data flow is one-way: Excel → Python
Python does not write back to Excel
4. Excel Schema Contract (Hard-Locked)
4.1 Column Authority Rules
Column names never change
Column order never changes
Python fails hard if schema drifts
Calculated columns are not manually edited
4.2 Excel Columns (All Preserved)
Ph
BLD
Unit
U_code
Status
Move_out
Ready_Date
DV (calendar-based, informational)
Move_in
DTBR (calendar-based, informational)
N/V/M
Insp
Insp_status
Paint
Paint_status
MR
MR_Status
HK
HK_Status
CC
CC_status
Assing
W/D
QC
Notes
5. Time & Date Semantics
5.1 Time Anchor
Excel TODAY() is authoritative
All logic is date-only
No time-of-day math exists anywhere
5.2 Date Normalization
All date columns are normalized
Any time component is stripped
Invalid strings → null
6. Working Days & SLA Model
6.1 Working Days
Monday–Friday only
Saturday & Sunday are non-working
6.2 SLA Definition
10 BUSINESS days from Move_out
Measured using a business-day counter
DV (calendar days) is display only
6.3 Move-In Day Counting
Move-in day is excluded
Only working days before move-in are counted
7. Task Workflow Model
7.1 Task Order (Fixed)
Inspection
Paint
MR
HK
CC
7.2 QC Handling
QC is not a task
QC is a quality / readiness gate
Final operational task = CC
7.3 Task Date Meaning
Task dates are due dates
Represent when work should happen
Not verification timestamps
7.4 Task Completion Rule
Only Status = "Done" means complete
Matching is case-insensitive
Done means work was visually verified
Verification may occur the next day
7.5 Task Skipping
Tasks are skipped by explicitly marking Done
Blank ≠ skipped
7.6 Blank Task Dates
Blank means:
not scheduled
not started
Typical for newly vacant or on-notice units
7.7 Parallel Statuses
Multiple tasks may share the same status
Dates differentiate progression, not status text
8. Current_Task Logic
8.1 General Rule
Current_Task = first task in sequence not marked Done
8.2 Edge Cases
All tasks Done → Complete
Status = Occupied or On Notice → blank / None
Insp Done, others blank → Paint
9. Turn & Occupancy Intelligence
9.1 Turn_State (Python)
Normalized from Excel Status:
Vacant Ready
Vacant Not Ready
On Notice
Occupied
Excel N/V/M remains intact and separate.
10. Priority Logic (URGENT vs OK)
10.1 Priority Definition
Priority is computed in Python only.
A unit is URGENT if any of the following are true:
Move-in pressure
Insufficient remaining working days
Vacant not ready SLA breach
10 business days since Move_out
Plan integrity broken
Ready_Date ≤ today and unit not ready
Quality block
QC ≠ Done when readiness is expected
10.2 “Not Ready” Definition
A unit is not ready if:
Turn_State != "Vacant Ready"
OR
QC != "Done"
10.3 Urgency Reasons
Multiple reasons allowed
Reasons are additive
Priority itself is binary
11. Ready_Date Semantics
Ready_Date is a planning promise
Pushing Ready_Date:
acknowledges delay
does not erase SLA history
Ready_Date in past with no move-in:
informational only
not urgent
not escalated
12. Suppression (False Urgency Protection)
12.1 Suppression Model
Visibility-only
Never alters truth, priority, or escalation
12.2 Suppression Source
Driven only by Notes keywords
Examples:
HOLD
LEGAL
PARTS
Case-insensitive substring match
Keyword list is extendable
12.3 Effects
Suppressed units:
hidden from cockpit / capped views
still appear in escalation views
still appear in raw tables
12.4 Explicit Non-Rules
W/D does not suppress
Task status does not suppress
13. Escalation Logic
13.1 Escalation Model
Plan-based
Separate from Priority
Binary Escalation_Flag
Optional Escalation_Level retained for severity tiers
13.2 Escalation Triggers
Escalation occurs when:
Ready_Date ≤ today and unit not ready
10-business-day SLA exceeded
14. Capacity & Visibility Logic (Step 9)
14.1 Purpose
Limit overload while never hiding move-ins at risk.
14.2 Core Rule
Move-ins always override caps.
If today is the last viable working day to meet a move-in, the unit is always shown.
14.3 Order of Operations
Hard Include (Uncapped)
Units that must be worked today
Suppression Filter
Per-Task Caps
Global Cap
14.4 Ranking Logic
Primary ranking:
Fewest remaining working days
Move_in date
Plan breach / escalation
Remaining working days logic is view-layer only.
15. “Not Today” Logic
There is no manual override.
A unit is “not today” only if:
Working days remain before move-in
Other units have fewer remaining working days
Examples:
Friday → Monday move-in → must work Friday
Monday → Thursday move-in → can wait
Sooner move-ins always outrank later ones.
16. Python Derived Columns (Augmentation Layer)
Python adds intelligence without removing Excel data, including:
Days_Vacant_Calc (business-day logic)
DTBR_Calc
Working_Days_To_MoveIn
Turn_State
Current_Task
Priority_Flag
Urgency_Reason
Suppressed_Flag
Suppressed_Reason
Escalation_Flag
Escalation_Level
SLA_Breach_Flag
Plan_Breach_Flag
QC_Block_Flag
Days_In_Current_Task (placeholder)
Forecast scaffolding fields (placeholders)
17. Phase 2 (Explicitly Not Implemented)
Present only as placeholders:
Days_In_Current_Task logic
Forecast Ready Date modeling
Predictive durations
Vendor repeat detection
Advanced escalation tiers
18. System Status
✅ All rules explicit
🔒 v1 frozen
🧠 Phase 2 can layer without refactor
🚀 Ready to build views
19. Final Verdict
Approved.Ship v1.Build views.Do not touch the engine.
Python Rule Pipeline
Engine Augmentation Layer (v1)
Purpose
This Python rule pipeline augments the Excel turnover table by adding deterministic logic, normalization, and decision flags without modifying or replacing any Excel calculations.
Excel remains the operational engine.
Python provides consistency, validation, prioritization, and visibility logic.
Pipeline Overview (Execution Order)
The pipeline runs in the following fixed order:
Load and validate Excel schema
Establish the “today” anchor
Normalize date and text inputs
Calculate business-day metrics
Derive workflow and task state
Apply readiness and QC rules
Apply suppression logic
Detect SLA and plan breaches
Compute priority and urgency
Compute escalation signals
Preserve Phase 2 placeholders
Prepare visibility and ranking flags
Each step is deterministic and idempotent.
1. Load Excel Data (Schema Locked)
The Excel table is loaded exactly as-is.
Column names and order are validated against the v1 contract.
If any column is missing, renamed, or reordered, execution fails immediately.
No Excel values are altered.
2. “Today” Anchor
The system uses a normalized date-only value for “today”.
Time of day is discarded.
All comparisons are date-based only.
Excel’s TODAY() concept is mirrored in Python.
3. Input Normalization
Date Normalization
All date columns are coerced into valid dates.
Invalid strings become null.
Time components are stripped.
Blank cells remain null.
Text Normalization
Task statuses and Notes are trimmed.
Case-insensitive comparisons are used.
Semantic meaning matters more than exact casing.
4. Business-Day Calculations
Working Day Definition
Monday through Friday only.
Saturdays and Sundays are excluded.
No holidays are considered in v1.
Calculated Metrics
Days_Vacant_Calc
Business days since Move_out (excluding today).
Working_Days_To_MoveIn
Business days from today to Move_in, excluding the move-in day itself.
These values are used for SLA enforcement, move-in pressure, and ranking.
5. Turn State Derivation
A normalized Turn_State is derived from Excel’s Status column:
Vacant Ready
Vacant Not Ready
On Notice
Occupied
This does not replace Excel’s N/V/M column.
It exists purely for logic consistency.
6. Current Task Determination
Task Order (Fixed)
Inspection
Paint
MR
HK
CC
Rules
If the unit is Occupied or On Notice, Current_Task is blank.
Otherwise, the current task is the first task not marked “Done”.
Status matching for “Done” is case-insensitive.
If all tasks are done, Current_Task = Complete.
Task Stalled Flag
A task is considered stalled if:
It is the current task, and
Its status is “Blocked” or “Not Started”.
7. Readiness and QC Logic
QC Interpretation
QC is not a task.
QC is a readiness gate.
Blank QC means “not evaluated yet”.
Readiness Expected
Readiness is expected when:
Ready_Date exists, and
Ready_Date is today or earlier.
Derived Flags
Not_Ready_Flag
True when:
Turn_State is not Vacant Ready, or
QC is not Done
QC_Block_Flag
True when readiness is expected and QC is not Done
Plan_Breach_Flag
True when readiness is expected and the unit is not ready
8. Suppression Logic (False Urgency Protection)
Source
Suppression is driven only by keywords found in Notes.
Keywords are case-insensitive substrings.
Examples: HOLD, LEGAL, PARTS.
Outputs
Suppressed_Flag (Yes/No)
Suppressed_Reason (keyword that triggered suppression)
Rules
Suppression affects visibility only.
Suppressed units:
Are hidden from cockpit views
Still appear in escalation and raw data views
9. SLA Breach Detection
SLA Definition
10 business days from Move_out.
Derived Flag
SLA_Breach_Flag
True when business days vacant exceed 10.
Calendar-based DV is ignored for enforcement and used only for display.
10. Priority Calculation (URGENT vs OK)
Priority is computed in Python only.
A unit is marked URGENT if any of the following are true:
Move-in pressure
Move-in exists
Remaining working days are insufficient
Unit is not ready
SLA breach
Unit is Vacant Not Ready
SLA_Breach_Flag is true
Plan breach
Ready_Date ≤ today
Unit is not ready
QC block
Readiness expected
QC not Done
Outputs
Priority_Flag: URGENT / OK
Urgency_Reason: One or more explanatory reasons
11. Escalation Logic
Escalation is separate from priority.
Escalation Rules
A unit is escalated when:
SLA_Breach_Flag is true, or
Plan_Breach_Flag is true
Outputs
Escalation_Flag (Yes/No)
Escalation_Level
v1 uses Level 1 only
Higher levels are reserved for Phase 2
Suppression does not block escalation visibility.
12. Phase 2 Placeholders (Intentionally Inactive)
These columns exist but are not populated in v1:
Days_In_Current_Task
Is_Repeat_Issue
Forecast_Ready_Date (mirrors Ready_Date)
Forecast_Delta_Days
At_Risk_Flag
Capacity_Weight
They allow future layering without refactoring.
13. Capacity & Visibility Flags (Step 9)
Must-Work-Today Logic
A unit must be worked today if:
It has a move-in, and
Remaining working days before move-in are zero or fewer, and
The unit is not ready
Visibility Rules
Must-work-today units are always visible.
Other urgent units are visible only if not suppressed.
Caps are applied later at the view level, not in the engine.
14. Ranking Keys (For Views)
To support consistent ordering, the engine provides:
Rank_WorkingDays
Fewer remaining working days rank higher.
Rank_MoveInDate
Earlier move-ins rank higher.
These are used by cockpit and planning views.
Final State
Excel remains unchanged and authoritative.
Python adds deterministic intelligence only.
All rules are explicit and reproducible.
The engine is frozen at v1.
Approved. Ready for view construction.