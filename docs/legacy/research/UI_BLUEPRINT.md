# Natural-Language UI Blueprint — The DMRB

This document is a complete visual and structural specification of the user interface. It is written in plain natural language so that another agent or developer can build a UI skeleton from this description without inspecting the repository. No gameplay or business logic is specified; only layout, placement, and what the user sees.

---

## Discovery Summary: UI-Related Files

| File path | UI component | What it represents visually |
|-----------|--------------|-----------------------------|
| `app.py` | Application shell | Full-page wide layout; global error banner; sidebar + main content area |
| `ui/components/sidebar.py` | Sidebar navigation | Left rail: app title, caption, radio list of eight pages |
| `ui/components/sidebar_flags.py` | Top Flags panel | Sidebar: divider, "Top Flags" heading, expanders per breach category with unit buttons |
| `ui/data/cache.py` (render_active_property_banner) | Active property banner | Main area: caption line showing current property name or info message |
| `ui/screens/board.py` | DMRB Board screen | Main area: bordered filter bar, metrics bar, two tabs (Unit Info table, Unit Tasks table) |
| `ui/screens/morning_workflow.py` | Morning Workflow screen | Main area: title, caption, four numbered sections with subheaders and content blocks |
| `ui/screens/flag_bridge.py` | Flag Bridge screen | Main area: bordered filter row, metrics row, single read-only data table with checkbox column |
| `ui/screens/risk_radar.py` | Risk Radar screen | Main area: subheader, caption, filter row (Phase, Risk Level, search), four metrics, one read-only table |
| `ui/screens/report_operations.py` | Report Operations screen | Main area: title, banner, three tabs (Missing Move-Out, FAS Tracker, Import Diagnostics) |
| `ui/screens/turnover_detail.py` | Turnover Detail screen | Main area: unit lookup or multi-panel detail (unit info, status, dates, W/D, risks, authority expander, tasks table, notes) |
| `ui/screens/ai_agent.py` | DMRB AI Agent screen | Main area: two-column layout — left: New Chat button + session list; right: chat messages and input |
| `ui/screens/admin.py` | Admin screen | Main area: subheader, three-column control bar (DB Writes checkbox, property selector, new property input), captions, five tabs (Add Unit, Import, Unit Master Import, Exports, Dropdown Manager) |
| `ui/screens/unit_import.py` | Unit Master Import (embedded in Admin) | Tab content: subheader, caption, strict-mode checkbox, file uploader, run button, result message, table of imported units |
| `ui/screens/exports.py` | Exports (embedded in Admin) | Tab content: subheader, caption, prepare button, two columns of download buttons |

---

## UI SYSTEM OVERVIEW

The interface is a single-page web application with a **wide layout**: the browser window is used at full width. There are two main layers:

1. **Sidebar (left rail)**  
   A fixed vertical strip on the left. It always shows the application title, a short caption, and a list of eight navigation options displayed as a single-selection radio group. Below that, a horizontal divider and a "Top Flags" section made of expandable blocks; each block shows a category label with a count and a short list of clickable unit entries. The sidebar does not scroll away; it is always visible.

2. **Main content area (right of sidebar)**  
   The rest of the screen is the main area. Its content is determined by the selected navigation item. Every screen in the main area can show an **active property banner** at the top: a single line of text (caption style) that either shows "Active Property: [name]" or an informational message asking the user to create a property in Admin. Below that, screen-specific content fills the main area (titles, filter bars, metrics, tables, forms, tabs, or chat).

There is **no separate main menu screen**. The application opens directly with the sidebar visible and the main area showing one of the eight screens (by default, the DMRB Board). There are **no overlays** such as pause, modal dialogs, or game-over screens; all content is inline in the main area or in the sidebar. Error and success messages appear inline (e.g. error banners at top of main area, or messages above/below the relevant controls).

**Global styling:** Table and dataframe cells use centered text. Metric values and labels are centered. Vertical block text (e.g. in containers) is centered except for form labels (select box, text input, date input, text area), which remain left-aligned. Data table columns are auto-sized to content.

---

## SCREEN-BY-SCREEN LAYOUT

### Application shell (every screen)

- **Sidebar (left):**  
  - Top: A title line: "The DMRB".  
  - Directly under: A caption line: "Apartment Turn Tracker".  
  - Then: A "Navigate" label and a vertical list of eight options as a single-selection radio: "Morning Workflow", "DMRB Board", "Flag Bridge", "Risk Radar", "Report Operations", "Turnover Detail", "DMRB AI Agent", "Admin". One item is selected at a time.  
  - A horizontal divider.  
  - A bold line: "Top Flags".  
  - If the database is unavailable: an error message in the sidebar.  
  - Otherwise: up to four expandable sections. Each section has a title like "Insp Breach (n)", "SLA Breach (n)", "SLA MI Breach (n)", "Plan Breach (n)" with a count in parentheses. Inside each expander are up to five buttons; each button shows a unit code and optionally "DV" and a number. If there are no flagged units, a short caption like "No flagged units" appears instead.  

- **Main area (right):**  
  - If the backend failed to load: a full-width error message at the very top and the app stops rendering.  
  - Otherwise: the active property banner (one caption line), then the content of the currently selected screen.

---

### Morning Workflow screen

The user sees a large title "Morning Workflow" at the top of the main area, then a caption line: "What do I need to fix right now before the day starts?". Then the active property banner. If there is no active property, nothing else is shown.

Otherwise, the rest of the screen is a vertical stack of four sections, each with a subheader and caption, separated by horizontal dividers:

1. **Section "1. Import Status"**  
   Subheader: "1. Import Status". Caption: "Confirm reports are fresh before starting the day." Then a list of lines: for each of Move-Out, Move-In, Available, FAS, either a warning line (e.g. "report not imported today") or a text line with label and timestamp. If no imports exist, an info message is shown.

2. **Section "2. Units missing move-out date"**  
   Subheader: "2. Units missing move-out date". Caption about repair queue. Then either a success message or a table (columns: Unit, Move-In Date, Report). Below the table, a bold line "Resolve: create turnover with move-out date", then a dropdown "Select unit to resolve", a date picker "Move-out date", and a button "Create turnover".

3. **Section "3. Turnover risk summary"**  
   Subheader: "3. Turnover risk summary". Caption. Three metrics in a row: "Units vacant > 7 days", "Units with SLA breach", "Move-ins within 3 days". Optionally a button "Open Flag Bridge (SLA breach filter)" and a button "Open DMRB Board".

4. **Section "4. Today's critical units"**  
   Subheader: "4. Today's critical units". Caption about move-ins, move-outs, ready dates. Either an info message or a table (Unit, Event, Date). Then caption "Open a unit in Turnover Detail:", a dropdown "Select unit", and a button "Open Turnover Detail".

---

### DMRB Board (gameplay / primary work screen)

The user sees the active property banner. If there is no active property, nothing else is shown. Otherwise:

- **First bordered container (filter bar):**  
  One row with eight columns. Column 1 (wider): a text input labeled "Search unit". Columns 2–6: five dropdowns in order — "Phase", "Status", "N/V/M", "Assign", "QC". Column 7: a metric "Active" (number). Column 8: a metric "CRIT" (number).

- **Second bordered container (metrics bar):**  
  One row with six equal columns. Each column shows a metric: "Active Units", "Violations", "Plan Breach", "SLA Breach", "Move-In Risk", "Work Stalled".

- If there are no rows matching filters, an info message "No turnovers match filters." is shown and the screen stops there.

- **Tabs:**  
  Two tabs: "Unit Info" and "Unit Tasks".

  - **Unit Info tab:** A single data grid (spreadsheet-like). Columns include: a checkbox column, Unit, Status, Move-Out, Ready Date, DV, Move-In, DTBR, N/V/M, W/D, Quality Control, Alert, Notes. Rows are one per turnover. Some columns are editable (e.g. Status, dates, Quality Control) when writes are enabled; others are read-only.

  - **Unit Tasks tab:** A single data grid. Columns include: checkbox, Unit, a small symbol column, Status, DV, DTBR, then for each task type (Inspection, Carpet Bid, Make Ready Bid, Paint, Make Ready, Housekeeping, Carpet Clean, Final Walk) a status column and a date column. Same row count as Unit Info. Selecting the checkbox in a row and applying changes can navigate to Turnover Detail for that unit.

---

### Flag Bridge screen

The user sees the active property banner. If there is no active property, nothing else is shown. Otherwise:

- **First bordered container:** One row of six equal columns, each a dropdown: "Phase", "Status", "N/V/M", "Assign", "Flag Bridge", "Value".

- **Second bordered container:** One row of three metrics: "Total Units", "Violations", "Units w/ Breach".

- If no rows match filters, an info message is shown. Otherwise, a single data table (read-only) with columns: checkbox, Unit, Status, DV, Move-In, Alert, and several narrow columns (Viol, Insp, SLA, MI, Plan) showing a symbol or dash. Checking the checkbox in a row navigates to Turnover Detail for that unit.

---

### Risk Radar screen

The user sees a subheader "Turnover Risk Radar" and a caption "Units most likely to miss readiness or move-in deadlines." Then the active property banner. If there is no active property, nothing else is shown. Otherwise:

- **Filter row:** Three columns. Column 1: dropdown "Phase". Column 2: dropdown "Risk Level" (All, HIGH, MEDIUM, LOW). Column 3: text input "Unit Search".

- **Metrics row:** Four equal columns: "Total Active Turnovers", "High Risk", "Medium Risk", "Low Risk".

- If no rows match, an info message is shown. Otherwise, a single read-only table with columns: Unit, Phase, Risk Level (with color-style text), Risk Score, Risk Reasons, Move-in Date.

---

### Report Operations screen

The user sees a title "Report Operations" and the active property banner. If there is no active property, nothing else is shown. Otherwise, three tabs:

- **Tab "Missing Move-Out":** Subheader "Missing Move-Out Queue", caption, then either an info message or a table (Unit, Report type, Move-in date, Conflict reason, Import timestamp). Then a horizontal rule, bold "Resolve: create turnover with move-out date", dropdown "Select unit to resolve", date input "Move-out date", button "Create turnover".

- **Tab "FAS Tracker":** Subheader "Final Account Statement Tracker", caption, then either an info message or a table (Unit, FAS date, Import timestamp, Note). Then a horizontal rule, bold "Edit note", dropdown "Select row", text input "Note", button "Save note".

- **Tab "Import Diagnostics":** Subheader "Import Diagnostics", caption, then either an info message or a table (Unit, Report type, Status, Conflict reason, Import time, Source file).

---

### Turnover Detail screen

The user sees the active property banner. Then either the **unit lookup state** or the **full detail state**.

**Unit lookup state (no unit selected):**  
Subheader "Turnover Detail", a text input "Unit code", and a button "Go". If the user clicks Go and the unit is not found, a warning appears; if found, the screen switches to the full detail state for that unit.

**Full detail state (unit selected):**  
A vertical stack of bordered containers and one expander:

- **Panel A — Unit information:**  
  Bold "UNIT INFORMATION". One row: left (wider) shows a heading with unit code and a small green or red dot (legal confirmation). Right: a "← Back" button. Next row: five columns showing Phase, Building, Unit, N/V/M, Assignee as label-value pairs.

- **Panel B — Status and QC:**  
  One row: left, a "Status" dropdown; right, a primary button "Confirm Quality Control".

- **Panel C — Dates:**  
  Bold "DATES". One row of five columns: Move-Out (date input), DV (number or highlighted if high), Ready Date (date input), Move-In (date input), DTBR (number).

- **Panel D — W/D status:**  
  Bold "W/D STATUS". Three columns: "Present" (dropdown: No / Yes / Yes stack), "Notified" (text and optional "Mark Notified" button), "Installed" (text and optional "Mark Installed" button).

- **Panel E — Risks:**  
  Bold "RISKS". List of risk lines (icon, type, severity, description) or caption "No active risks".

- **Panel E2 — Authority and import comparison:**  
  An expander titled "Authority & Import Comparison" (optional warning suffix). When expanded: a table-like layout with columns Field, Current (System), Last Import, Source, Override, and for some rows a "Clear" button.

- **Panel F — Tasks:**  
  Bold "TASKS". Header row: Task, Assignee, Date, Execution, Confirm, Req, Blocking. Then a divider and one row per task: task name, assignee dropdown, date input, execution dropdown, confirmation dropdown, required checkbox, blocking dropdown.

- **Panel G — Notes:**  
  Bold "NOTES". List of note lines (description, type, optional "Resolve" button). Then a text area "Add note (free text)" and a button "Add note".

---

### DMRB AI Agent screen (console / chat)

The user sees a subheader "DMRB AI Agent" and a caption "AI can make mistakes. Check important info." Then a two-column layout:

- **Left column (narrow):**  
  A full-width button "+ New Chat". Under it, a heading "Sessions". Then either a caption "No chat sessions yet." or a list of session entries. Each entry is a row: one button showing the session title (and a dot if selected) and a second button with a trash icon. Clicking the title button loads that session; clicking the trash deletes it.

- **Right column (wide):**  
  If no session is loaded and there are no messages: a heading "DMRB AI Agent" and a grid of suggestion buttons (two columns of short question texts).  
  If there are messages: each message is shown in a chat bubble (user on one side, assistant on the other) with the message content.  
  At the bottom of the right column: a chat input placeholder "Ask anything about turnovers...". There is no separate "Run" button; sending is done via the chat input.

Errors (e.g. API unreachable) appear as error messages in the main area above or within this layout.

---

### Admin screen

The user sees a subheader "Admin". Then a **control bar** in three columns:

- **Column 1:** A checkbox "Enable DB Writes (irreversible)".
- **Column 2:** A dropdown "Active Property" listing properties by name and id, or a caption if none exist.
- **Column 3:** A text input "New Property" (placeholder "Property name") and a button "Create Property".

Below the control bar, one or two caption lines (about DB writes and active property). Then **five tabs**: "Add Unit", "Import", "Unit Master Import", "Exports", "Dropdown Manager".

**Tab "Add Unit":**  
Subheader "Add unit", caption. Then Phase dropdown, Building dropdown, Unit text input, Move out date, Ready date (optional), Move in (optional), and "Add unit" button. (If no phases or buildings exist, the screen may show warnings and optional inputs to create phase or building.)

**Tab "Import":**  
Subheader "Import console". Four sub-tabs: "Available Units", "Move Outs", "Pending Move-Ins", "Final Account Statement (FAS)". In each sub-tab: a file uploader for the corresponding CSV, a "Run … import" button, then a heading for the latest import table, caption (import time, file, row count, status), and a table of the latest import rows. The Available Units sub-tab also has a button "Apply latest Available Units readiness to turnovers" and a "Conflicts" subheader with caption below.

**Tab "Unit Master Import":**  
Subheader "Unit Master Import", caption. A checkbox "Strict mode (fail if unit not found; no creates)", a file uploader "Units.csv", a button "Run Unit Master Import". Then a heading "Unit Master Import — Imported Units" and either a table of imported units or an info message.

**Tab "Exports":**  
Subheader "Export Reports", caption. A button "Prepare Export Files". Then either an info "Click 'Prepare Export Files' to generate downloads." or two columns of download buttons: column 1 — "Download Final Report (XLSX)", "Download DMRB Report (XLSX)", "Download Dashboard Chart (PNG)"; column 2 — "Download Weekly Summary (TXT)", "Download All Reports (ZIP)".

**Tab "Dropdown Manager":**  
Subheader "Dropdown Manager", caption. A bordered container "TASK ASSIGNEES" with expanders per task type; each expander lists assignees with a "Remove" button and has a text input "Add assignee" and "Add" button. Another bordered container "TASK OFFSET SCHEDULE" with one row per task: task name, "Offset" dropdown, "Save" button; then a divider and a list "Day N → Task name". A third bordered container "SYSTEM-CONTROLLED VALUES" with three columns of read-only labels (Execution Statuses, Confirmation Statuses, Blocking Reasons).

Admin also includes a "Property structure" section (read-only expanders per property showing phase → building → units).

---

## ELEMENT PLACEMENT

- **Sidebar:** Occupies a fixed width on the left (Streamlit default sidebar width). Title and caption at the top; navigation radio below; divider; "Top Flags" and expanders fill the rest. All sidebar content is left-aligned within the rail.

- **Active property banner:** Directly under the top of the main content area, full width, one line of caption-sized text. No border.

- **Filter bars:** Each screen that has filters uses a bordered container spanning the main area width. Filters are in a single row, one control per column; columns are proportioned (e.g. search wider, dropdowns equal, metrics at the end).

- **Metrics:** Shown in horizontal rows inside bordered containers. Each metric is a numeric value with a label; they are laid out in equal-width columns (e.g. 3, 4, or 6 per row). Metric values and labels are centered (per global CSS).

- **Data tables / data grids:** Full width of the main content area, below filters and metrics. Tables have no row index column. Cell text is centered. Column headers are centered. Editable tables show dropdowns or date pickers in cells where applicable.

- **Tabs:** Tab labels appear in a single row at the top of the tabbed region; the selected tab’s content fills the space below.

- **Buttons:** Placed inline with the related controls (e.g. "Create turnover" under the date input, "Add unit" at the end of the form). "← Back" is top-right of the first panel on Turnover Detail. "Confirm Quality Control" is in the status panel. Primary actions use the primary button style where specified.

- **Chat (AI Agent):** Left column is about one-quarter width, right column about three-quarters. Sessions list scrolls if long; chat messages stack vertically; input is fixed at the bottom of the right column.

- **Admin control bar:** Three columns span the main width; column 1 is slightly narrower than 2 and 3. Captions are full-width below the bar.

---

## UI STACK STRUCTURE

There are no overlapping overlay layers (no pause overlay, no modal). The visual stack is:

1. **Background:** The application page (white or theme background).
2. **Sidebar layer:** The left rail (title, caption, navigation, Top Flags) is always visible and does not overlay the main area.
3. **Main content layer:** The main area occupies everything to the right of the sidebar. Within it:
   - Optional global error banner at the very top (backend failed).
   - Active property banner (caption line).
   - Screen-specific content (filters, metrics, tables, forms, tabs, chat).

When the user changes the navigation selection, the main content is replaced entirely by the new screen; the sidebar does not change. No popovers or dropdown overlays are specified beyond standard form controls (dropdowns, date pickers).

---

## CONSOLE / TERMINAL LAYOUT

The application has no traditional code editor or terminal. Two areas are "console-like":

### DMRB AI Agent (chat console)

- **Session list (left):** Acts as the "session selector". "Sessions" heading at top. Each session is a button (title text, optionally with a selected-state dot). A trash button beside each. A "+ New Chat" button above the list.
- **Message area (right, top):** Where conversation appears. User messages and assistant messages are shown in distinct chat bubbles, stacked vertically, newest at the bottom.
- **Prompt / input (right, bottom):** A single chat input field with placeholder "Ask anything about turnovers...". There is no separate "Run" or "Send" button; submission is via the chat input (e.g. Enter).
- **Suggestions (right, when no messages):** When the conversation is empty, suggestion questions appear as buttons in a two-column grid above where messages would appear. Clicking a suggestion fills or sends the question.

### Admin Import console

- **Tabs:** Four report types (Available Units, Move Outs, Pending Move-Ins, FAS). Each tab is a separate "console" for that report.
- **File upload:** At the top of each tab, a file upload control for the corresponding CSV.
- **Run button:** Directly below the uploader, a button "Run [Report type] import". No separate code editor or command line.
- **Feedback:** After run, success or error messages appear inline below the button. For imports, a table "Latest import" appears with caption (import time, file, row count, status). Diagnostic or validation errors are listed as bullet points or numbered lines below the message.

---

## INVENTORY LAYOUT

The application does not have an inventory grid of items. It has **data tables** that resemble lists or grids of records (turnovers, units, tasks, import rows). Placement rules for those:

- **Grid structure:** Each table is one contiguous grid. Rows are data records; columns are fields. The first column is often a checkbox for "select this row" (e.g. to open detail or apply an action). No explicit "item slot" layout; each row is one slot.
- **Item preview:** There is no dedicated preview area. Row content is fully visible in the table cells (unit code, status, dates, etc.). Selecting a row (checkbox) typically navigates to Turnover Detail, which acts as the "detail view" for that record.
- **Item description:** On Turnover Detail, the "UNIT INFORMATION" panel and the "NOTES" panel serve as the description area for the selected unit. There is no separate floating description panel on the board or Flag Bridge; the table cells themselves show the key fields.

---

## UI COMPONENT LIST

1. **Application shell** — Wide layout, global error banner, sidebar + main area.
2. **Sidebar** — Left rail: title, caption, navigation radio, Top Flags.
3. **Top Flags** — Sidebar: divider, heading, expanders with unit buttons.
4. **Active property banner** — Main area: one caption line.
5. **Morning Workflow screen** — Title, caption, four numbered sections with subheaders and content.
6. **DMRB Board screen** — Filter bar, metrics bar, Unit Info / Unit Tasks tabs with data editors.
7. **Flag Bridge screen** — Filter row, metrics row, breach table.
8. **Risk Radar screen** — Subheader, filters, metrics, risk table.
9. **Report Operations screen** — Title, three tabs (Missing Move-Out, FAS Tracker, Import Diagnostics).
10. **Turnover Detail screen** — Unit lookup or multi-panel detail (unit info, status, dates, W/D, risks, authority expander, tasks table, notes).
11. **DMRB AI Agent screen** — Two-column chat: sessions list (left), messages and input (right).
12. **Admin screen** — Control bar (DB Writes, property selector, new property), five tabs (Add Unit, Import, Unit Master Import, Exports, Dropdown Manager).
13. **Add Unit form** — Admin tab: phase/building/unit dropdowns and date inputs, Add unit button.
14. **Import console** — Admin tab: four report-type sub-tabs, file uploader, run button, latest-import table per type.
15. **Unit Master Import** — Admin tab: strict checkbox, file uploader, run button, imported-units table.
16. **Exports** — Admin tab: prepare button, two columns of download buttons.
17. **Dropdown Manager** — Admin tab: task assignees expanders, task offset schedule, system-controlled values list.
18. **Property structure** — Admin: read-only expanders (property → phase → building → units).

---

*End of UI Blueprint. This document describes only visual structure, layout, and component hierarchy. No code is included.*
