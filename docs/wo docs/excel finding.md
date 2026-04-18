
Here is what can be concluded **from the two artifacts actually present in the workspace**:  
`wo docs/Active_Service_Request_Mabi_python_cells.txt` and `wo docs/Active_Service_Request_Robert_python_cells.txt`.

**Important limits**

- There are **no** `Active_Service_Request_Mabi` / `Active_Service_Request_Robert` workbook files (e.g. `.xlsx`) in this workspace, so **sheet tab names, visual grouping, colors, merged cells, and MRB-style layout cannot be read from disk here.**
- These `.txt` files are **Python-in-Excel cell scripts** (`xl(%P2%)`, column indices). They define **data shape and filters only**, not Excel formatting.
- Per your scope (“do not analyze any other files”), **Export Final Report** and **MRB format** cannot be compared to anything in-repo; sections 7–8 below separate **what the scripts imply** from **what is unknown without those templates.**

---

## 1. Sheets / tabs / views (inferred)

**Reasonable mapping:** In this pattern, **each “PYTHON CELL SCRIPT #N” is usually one output table** (one sheet, or one spilled range on a dashboard). Counts:

| Workbook (inferred from filename) | Python data scripts | Env block |
|-----------------------------------|---------------------|-----------|
| Mabi | **28** scripts (#1–#28) | Shared init |
| Robert | **21** scripts (#1–#21) | Same init |

So **Mabi has 7 more distinct filtered views** than Robert, unless some scripts are reused on the same sheet (not visible in these files).

**Exact tab names** are **not** in these files.

---

## 2. Exact filters per script (summary)

**Source layout (both):**  
- Phase: column index **0** (`df.iloc[:, 0]`, stripped string)  
- Assigned: index **9**  
- Status: index **11**  
- Output columns: **[4, 9, 2, 8, 11]** → `Unit`, `Assigned to`, `Days open`, `Issue`, `Status`

### Mabi — filters by script

| # | Phase | Assigned | Status | Notes |
|---|--------|----------|--------|--------|
| 1 | 3, 4, 4c | — | — | Phase only |
| 2 | 3, 4, 4c | Unassigned or "" | — | |
| 3 | 3 only | Unassigned or "" | — | |
| 4 | 4 only | Unassigned or "" | — | |
| 5 | 4c only | Unassigned or "" | — | |
| 6 | — | **equals "Mabi"** (post-rename) | — | Not phase-filtered |
| 7–11 | — | One name each (Dennis, Rayniel, Alexander, Diego, Victor) | **In progress** | |
| 12 | 4 | Unassigned or "" | — | Same logic as #4 |
| 13 | 4c | Unassigned or "" | — | Same logic as #5 |
| 14 | — | Alexander | **On hold** | No phase |
| 15 | 3 | **Unassigned** only (not "") | — | Stricter than #3 |
| 16–19 | 3 | Victor / Dennis | In progress or On hold | Phase + person + status |
| 20 | — | Rayniel | **On hold** | No phase |
| 21–28 | Mix | Unassigned by phase 4/4c; Diego/Dennis/Victor with phase 4 or 4c | In progress / On hold | See detail below |

**Mabi #21–#28 (compact):** Unassigned+4; Diego+4+In progress; Diego+4+On hold; Dennis+4+In progress/On hold; Victor+4c+In progress/On hold; Unassigned+4c.

### Robert — filters by script

| # | Phase | Assigned | Status | Notes |
|---|--------|----------|--------|--------|
| 1 | — | — | — | Full list (columns only) |
| 2 | — | **Unassigned** | — | |
| 3 | **5, 7, 8** | — | — | Phase-only rollup |
| 4 | 5, 7, 8 | Unassigned or "" | — | |
| 5 | **3, 4, 4c** | — | — | Different phase group than #3 |
| 6 | 3, 4, 4c | Unassigned or "" | — | |
| 7 | — | **Roberto Palacios** | — | Manager row (like Mabi #6) |
| 8–11 | — | Latrell, Yomar, Barron, Antonio | **In progress** | |
| 12–14 | **5 / 7 / 8** (one each) | Unassigned or "" | — | Phase split |
| 15–16 | — | Latrell | **On hold**; then Unassigned+**5** | |
| 17–18 | — | Yomar, Barron | **On hold** | |
| 19–21 | Unassigned+**7**; Antonio **On hold**; Unassigned+**8** | | | |

**Headline:** Mabi’s world is built around **3 / 4 / 4c** plus a second set of views for **4 / 4c** with named techs. Robert mixes **5 / 7 / 8** (with its own rollups) **and** **3 / 4 / 4c** — **two different phase “portfolios” in one workbook**, which Mabi’s script set does not mirror.

---

## 3. Phases, assigned names, statuses, sorting

**Phases**

- **Mabi:** Almost everything is **3, 4, 4c** (string match after strip). No 5/7/8 in Mabi’s file.
- **Robert:** Uses **5, 7, 8** heavily **and** **3, 4, 4c** — so phase semantics are **portfolio- or manager-specific**, not universal in these two files.

**Assigned-to**

- **Shared literals:** `"Unassigned"`, `""` (empty treated as unassigned in many masks).
- **Mabi-specific names:** Dennis Arevalo, Rayniel Rincon, Alexander Gonzalez, Diego Zapata, Victor Castaneda, plus **`"Mabi"`** as assignee filter.
- **Robert-specific names:** Latrell Dawson, Yomar Gonzalez, Barron Russell, Antonio Sherfield, **`Roberto Palacios`**.

**Statuses**

- Only **two** values appear in filters: **`In progress`** and **`On hold`** (exact strings on column 11).

**Sorting**

- **Every** script ends with **`Days open` descending** and **`reset_index(drop=True)`**.  
- No secondary sort key appears in these files.

---

## 4. Exact Mabi vs Robert differences (data logic)

1. **Phase coverage:** Mabi = **3/4/4c** only. Robert = **5/7/8** and **3/4/4c** (two families).
2. **Script count:** Mabi **28** vs Robert **21** views.
3. **“Manager personal” row:** Mabi **`Assigned to == "Mabi"`**; Robert **`Roberto Palacios`** — same *pattern*, different name.
4. **Team grids:** Completely different rosters for **In progress** / **On hold** slices.
5. **Robert #1** is **unfiltered** (all phases); Mabi **never** has a no-phase, no-assigned “full export” equivalent in #1 — Mabi #1 already restricts to **3/4/4c**.
6. **Unassigned handling:** Robert #2 uses **only** `"Unassigned"`. Mabi often uses **`["Unassigned", ""]`**; Mabi #15 uses **only** `"Unassigned"` for Unassigned+phase 3 — **inconsistent** across Mabi scripts.

---

## 5. Shared output pattern

- Same **five output columns** and names.
- Same **sort:** `Days open` **descending**.
- Same **normalization** style: `strip()` on phase/status/assigned where filters exist; `fillna("")` before string ops on assigned/status.
- Same **“control tile”** structure in many cells: build masks → `df.loc[final_mask, cols]` → rename → sort → reset index → `df_view`.
- **Person + status** views: `assigned_mask & status_mask` (sometimes `& phase_mask`).

---

## 6. What generalizes vs stays manager-specific

**Generalizable (one report builder)**

- Column projection: indices **[4, 9, 2, 8, 11]** and header names.
- Standard sort and index reset.
- Filter building blocks: phase list, assigned list (including empty), status list, AND composition.
- Normalization helpers for string compare.

**Manager-specific (config per portfolio)**

- **Which phase sets** apply (Mabi: 3/4/4c only; Robert: 5/7/8 vs 3/4/4c split).
- **Roster** (names for In progress / On hold sections).
- **“My work” row** string (`Mabi` vs `Roberto Palacios`).
- **Which combinations** get a dedicated view (Robert has a **full unfiltered** table; Mabi does not in script #1).
- **Count and order** of sections (28 vs 21).

---

## 7. Comparison to Export Final Report & MRB format

**Not available from the four allowed artifacts.**  
These `.txt` files do not describe:

- Sheet names or order  
- Section titles, blank spacer rows, or grouping headers  
- Print areas, freeze panes, column widths, fonts, colors  
- “MRB-style” banding or table borders  

So **no honest line-by-line comparison** to Export Final Report or MRB is possible **without** those templates or workbooks.

**Indirect inference:** The Python side is **tabular only** (five columns, one sort). Any MRB-style **presentation** must live in **Excel layout around** these spills, not in these scripts.

---

## 8. Formatting / layout patterns “to match MRB” (from what we have)

**From scripts alone, the only portable “rules” are:**

- **Table schema:** `Unit | Assigned to | Days open | Issue | Status`
- **Row order:** longest-open first (`Days open` desc)
- **Filter semantics:** string equality on normalized phase/assigned/status

**Cannot be asserted from these files:**

- Visual grouping, repeated headers per section, summary rows, charts, or alignment with other reports.

---

## Shared output rules (data)

- Output columns and order fixed as above.  
- Always sort by **`Days open` descending**.  
- Strip phase; trim assigned/status; treat missing assigned as `""` where masks use it.

## Manager-specific rules (data)

- Phase universe (3/4/4c vs 5/7/8 + mixed).  
- Team member names and which get **In progress** vs **On hold** slices.  
- Manager self-filter string (`Mabi` vs `Roberto Palacios`).  
- Whether to include a **global unfiltered** table (Robert yes; Mabi no in #1).

## Exact sheet structure

- **Not specified** in these files; only **28 vs 21** logical tables can be inferred.

## Required MRB-style formatting

- **Not encoded** in these scripts — **unknown** from allowed files.

## Inconsistencies / risks

1. **Mabi #12–#13** duplicate **#4–#5** (same filters) — risk of **duplicate sheets** or copy-paste drift.  
2. **Unassigned:** mix of `["Unassigned", ""]` vs **`"Unassigned"` only** (Mabi #15 vs others) — **empty assignees** may **drop in/out** of views.  
3. **Robert #2** comment says “only Unassigned” but code uses **`== "Unassigned"`** — may **exclude** blank assigned rows that other scripts include via `""`.  
4. **Phase values** are strings (`"4c"`) — any Excel formatting of phase (e.g. numeric 4 vs `"4"`) could break `isin` if not normalized upstream.  
5. **No workbook files in repo** — sheet naming and MRB parity **cannot be verified** here.

If you add the actual **Mabi/Robert .xlsx** files (or export sheet names) to the project, a sheet-by-sheet and layout comparison becomes possible; in Ask mode I can only work from what is readable, which today is **these two `.txt` scripts only**.

Below is a **complete reconstruction** from only these four artifacts:

- `wo docs/Active_Service_Request_Mabi_python_cells.txt`
- `wo docs/Active_Service_Request_Robert_python_cells.txt`
- `wo docs/Active Service Request Mabi.xlsx`
- `wo docs/Active Service Request Robert  .xlsx`

**Excel ↔ Python wiring (authoritative):**  
Each Python script `#N` is invoked as:

`=_xlfn._xlws.PY(N-1, 0, SEV_REQUEST[])`

So **Python script number = Excel `PY` first argument + 1**. The input table is **`SEV_REQUEST[]`** (Excel table on `ServiceRequest`).

---

# PART 1 — PYTHON CELL ANALYSIS (LOGIC LAYER)

**Common to every script (unless noted):**

- Input: `df = xl(%P2%)` (same source range).
- Output columns (by index `[4, 9, 2, 8, 11]`): `Unit`, `Assigned to`, `Days open`, `Issue`, `Status`.
- Sort: `Days open` **descending**.
- `reset_index(drop=True)` after sort.

**Phase column:** `df.iloc[:, 0]` → `astype(str).str.strip()` where used.  
**Assigned column:** index `9` → `fillna("").astype(str).str.strip()` where used.  
**Status column:** index `11` → `fillna("").astype(str).str.strip()` where used.

---

## MABI — Python scripts 1–28

**Page 1 — Python script #1**  
- **Name:** All phases **3, 4, 4c** (no assigned/status filter).  
- **Filters:**  
  - Phase ∈ `{"3","4","4c"}`  
  - Assigned: *none*  
  - Status: *none*  
  - Unassigned vs empty: *not applied*  
- **Notes:** Standalone logical table.  
- **Grouped in Excel:** `Full_unassign!B5` → `PY(0,...)`.

---

**Page 2 — Python script #2**  
- **Name:** Global **Unassigned** list (strict string).  
- **Filters:**  
  - Phase: *none*  
  - Assigned: `Assigned to == "Unassigned"` **only** (does **not** treat `""` as Unassigned).  
  - Status: *none*  
- **Notes:** Standalone. **Differs** from scripts that use `["Unassigned", ""]`.  
- **Excel:** `Full_unassign!H5` → `PY(1,...)`.

---

**Page 3 — Python script #3**  
- **Name:** Phase **3** + Unassigned **or** empty assigned.  
- **Filters:**  
  - Phase ∈ `{"3"}`  
  - Assigned ∈ `{"Unassigned", ""}`  
  - Status: *none*  
- **Notes:** Standalone logic; **same script is placed twice** in Excel (see Part 2).  
- **Excel:** `Full_unassign!N5` **and** `unassign!B4` → both `PY(2,...)`.

---

**Page 4 — Python script #4**  
- **Name:** Phase **4** + Unassigned or empty.  
- **Filters:** Phase `{"4"}`; Assigned `{"Unassigned",""}`; Status *none*.  
- **Notes:** Standalone.  
- **Excel:** `Full_unassign!T5` → `PY(3,...)`.

---

**Page 5 — Python script #5**  
- **Name:** Phase **4c** + Unassigned or empty.  
- **Filters:** Phase `{"4c"}`; Assigned `{"Unassigned",""}`; Status *none*.  
- **Notes:** Standalone.  
- **Excel:** `Full_unassign!Z5` → `PY(4,...)`.

---

**Page 6 — Python script #6**  
- **Name:** Rows assigned to **`Mabi`**.  
- **Filters:**  
  - Phase: *none*  
  - Assigned: **exact** `"Mabi"` **after** column rename (filter on column `"Assigned to"`).  
  - Status: *none*  
- **Notes:** Standalone; not phase-scoped.  
- **Excel:** `By tech !B4` → `PY(5,...)`.

---

**Page 7 — Python script #7**  
- **Name:** **Dennis Arevalo** + **In progress**.  
- **Filters:** Assigned `{"Dennis Arevalo"}`; Status `{"In progress"}`; Phase *none*.  
- **Notes:** Standalone.  
- **Excel:** `By tech !H4` → `PY(6,...)`.

---

**Page 8 — Python script #8**  
- **Name:** **Rayniel Rincon** + **In progress**.  
- **Filters:** Assigned `{"Rayniel Rincon"}`; Status `{"In progress"}`.  
- **Notes:** Standalone.  
- **Excel:** `By tech !N4` → `PY(7,...)`.

---

**Page 9 — Python script #9**  
- **Name:** **Alexander Gonzalez** + **In progress**.  
- **Filters:** Assigned `{"Alexander Gonzalez"}`; Status `{"In progress"}`.  
- **Notes:** Standalone.  
- **Excel:** `By tech !T4` → `PY(8,...)`.

---

**Page 10 — Python script #10**  
- **Name:** **Diego Zapata** + **In progress**.  
- **Filters:** Assigned `{"Diego Zapata"}`; Status `{"In progress"}`.  
- **Notes:** Standalone.  
- **Excel:** `By tech !Z4` → `PY(9,...)`.

---

**Page 11 — Python script #11**  
- **Name:** **Victor Castaneda** + **In progress**.  
- **Filters:** Assigned `{"Victor Castaneda"}`; Status `{"In progress"}`.  
- **Notes:** Standalone.  
- **Excel:** `By tech !AF4` → `PY(10,...)`.

---

**Page 12 — Python script #12**  
- **Name:** Phase **4** + Unassigned or empty (**duplicate of script #4**).  
- **Filters:** Identical to script #4.  
- **Notes:** **Duplicate logic** in source text.  
- **Excel:** `unassign!H4` → `PY(11,...)`.

---

**Page 13 — Python script #13**  
- **Name:** Phase **4c** + Unassigned or empty (**duplicate of script #5**).  
- **Filters:** Identical to script #5.  
- **Notes:** **Duplicate logic** in source text.  
- **Excel:** `unassign!N4` → `PY(12,...)`.

---

**Page 14 — Python script #14**  
- **Name:** **Alexander Gonzalez** + **On hold** (no phase).  
- **Filters:** Assigned `{"Alexander Gonzalez"}`; Status `{"On hold"}`.  
- **Notes:** Standalone.  
- **Excel:** `Phase 3!H5` → `PY(13,...)`.

---

**Page 15 — Python script #15**  
- **Name:** Phase **3** + **Unassigned** only (excludes empty string).  
- **Filters:** Assigned `{"Unassigned"}` **only**; Phase `{"3"}`.  
- **Notes:** Stricter than script #3 for assigned (no `""`).  
- **Excel:** `Phase 3!N5` → `PY(14,...)`.

---

**Page 16 — Python script #16**  
- **Name:** Phase **3** + **Victor Castaneda** + **In progress**.  
- **Filters:** Phase `{"3"}`; Assigned `{"Victor Castaneda"}`; Status `{"In progress"}`.  
- **Notes:** Standalone.  
- **Excel:** `Phase 3!T5` → `PY(15,...)`.

---

**Page 17 — Python script #17**  
- **Name:** Phase **3** + **Victor Castaneda** + **On hold**.  
- **Filters:** Phase `{"3"}`; Assigned `{"Victor Castaneda"}`; Status `{"On hold"}`.  
- **Notes:** Standalone.  
- **Excel:** `Phase 3!Z5` → `PY(16,...)`.

---

**Page 18 — Python script #18**  
- **Name:** Phase **3** + **Dennis Arevalo** + **In progress**.  
- **Filters:** Phase `{"3"}`; Assigned `{"Dennis Arevalo"}`; Status `{"In progress"}`.  
- **Notes:** Standalone.  
- **Excel:** `Phase 3!AF5` → `PY(17,...)`.

---

**Page 19 — Python script #19**  
- **Name:** Phase **3** + **Dennis Arevalo** + **On hold**.  
- **Filters:** Phase `{"3"}`; Assigned `{"Dennis Arevalo"}`; Status `{"On hold"}`.  
- **Notes:** Standalone.  
- **Excel:** `Phase 3!AL5` → `PY(18,...)`.

---

**Page 20 — Python script #20**  
- **Name:** **Rayniel Rincon** + **On hold** (no phase).  
- **Filters:** Assigned `{"Rayniel Rincon"}`; Status `{"On hold"}`.  
- **Notes:** Standalone.  
- **Excel:** `Phase 4!H5` → `PY(19,...)`.

---

**Page 21 — Python script #21**  
- **Name:** Phase **4** + **Unassigned** only.  
- **Filters:** Assigned `{"Unassigned"}`; Phase `{"4"}`.  
- **Notes:** Stricter assigned than script #4/#12 (`""` not included).  
- **Excel:** `Phase 4!N5` → `PY(20,...)`.

---

**Page 22 — Python script #22**  
- **Name:** Phase **4** + **Diego Zapata** + **In progress**.  
- **Filters:** Phase `{"4"}`; Assigned `{"Diego Zapata"}`; Status `{"In progress"}`.  
- **Notes:** Standalone.  
- **Excel:** `Phase 4!T5` → `PY(21,...)`.

---

**Page 23 — Python script #23**  
- **Name:** Phase **4** + **Diego Zapata** + **On hold**.  
- **Filters:** Phase `{"4"}`; Assigned `{"Diego Zapata"}`; Status `{"On hold"}`.  
- **Notes:** Standalone.  
- **Excel:** `Phase 4!Z5` → `PY(22,...)`.

---

**Page 24 — Python script #24**  
- **Name:** Phase **4** + **Dennis Arevalo** + **In progress**.  
- **Filters:** Phase `{"4"}`; Assigned `{"Dennis Arevalo"}`; Status `{"In progress"}`.  
- **Notes:** Standalone.  
- **Excel:** `Phase 4!AF5` → `PY(23,...)`.

---

**Page 25 — Python script #25**  
- **Name:** Phase **4** + **Dennis Arevalo** + **On hold**.  
- **Filters:** Phase `{"4"}`; Assigned `{"Dennis Arevalo"}`; Status `{"On hold"}`.  
- **Notes:** Standalone.  
- **Excel:** `Phase 4!AL5` → `PY(24,...)`.

---

**Page 26 — Python script #26**  
- **Name:** Phase **4c** + **Victor Castaneda** + **In progress**.  
- **Filters:** Phase `{"4c"}`; Assigned `{"Victor Castaneda"}`; Status `{"In progress"}`.  
- **Notes:** Standalone.  
- **Excel:** `Phase 4c!B5` → `PY(25,...)`.

---

**Page 27 — Python script #27**  
- **Name:** Phase **4c** + **Victor Castaneda** + **On hold**.  
- **Filters:** Phase `{"4c"}`; Assigned `{"Victor Castaneda"}`; Status `{"On hold"}`.  
- **Notes:** Standalone.  
- **Excel:** `Phase 4c!H5` → `PY(26,...)`.

---

**Page 28 — Python script #28**  
- **Name:** Phase **4c** + **Unassigned** only.  
- **Filters:** Assigned `{"Unassigned"}`; Phase `{"4c"}`.  
- **Notes:** Stricter than script #5/#13 for assigned.  
- **Excel:** `Phase 4c!N5` → `PY(27,...)`.

---

**Standalone vs grouped:**  
Each script is a **standalone** logical table (one `df_view`). In the workbook they are **grouped visually** on shared sheets as **multiple side-by-side tables** (Part 2).

---

## ROBERT — Python scripts 1–21

**Page 1 — Python script #1**  
- **Name:** **No filter** — all rows (only column subset + sort).  
- **Filters:** Phase *none*; Assigned *none*; Status *none*.  
- **Notes:** Standalone.  
- **Excel:** `Full_unassign!B5` → `PY(0,...)`.

---

**Page 2 — Python script #2**  
- **Name:** **Unassigned** strict.  
- **Filters:** `Assigned to == "Unassigned"` only.  
- **Notes:** Same pattern as Mabi #2.  
- **Excel:** `Full_unassign!H5` → `PY(1,...)`.

---

**Page 3 — Python script #3**  
- **Name:** Phases **5, 7, 8** only.  
- **Filters:** Phase ∈ `{"5","7","8"}`; Assigned *none*; Status *none*.  
- **Notes:** Standalone.  
- **Excel:** `Full_unassign!N5` → `PY(2,...)`.

---

**Page 4 — Python script #4**  
- **Name:** Phases **5, 7, 8** + Unassigned or empty.  
- **Filters:** Phase `{"5","7","8"}`; Assigned `{"Unassigned",""}`.  
- **Notes:** Standalone.  
- **Excel:** `Full_unassign!T5` → `PY(3,...)`.

---

**Page 5 — Python script #5**  
- **Name:** Phases **3, 4, 4c** only.  
- **Filters:** Phase `{"3","4","4c"}`; no assigned/status.  
- **Notes:** Standalone.  
- **Excel:** `Full_unassign!Z5` → `PY(4,...)`.

---

**Page 6 — Python script #6**  
- **Name:** Phases **3, 4, 4c** + Unassigned or empty.  
- **Filters:** Phase `{"3","4","4c"}`; Assigned `{"Unassigned",""}`.  
- **Notes:** Standalone.  
- **Excel:** `Full_unassign!AF5` → `PY(5,...)`.

---

**Page 7 — Python script #7**  
- **Name:** **Roberto Palacios** rows.  
- **Filters:** `Assigned to == "Roberto Palacios"` after rename; Phase/Status *none*.  
- **Notes:** Standalone.  
- **Excel:** `By tech !B4` → `PY(6,...)`.

---

**Page 8 — Python script #8**  
- **Name:** **Latrell Dawson** + **In progress**.  
- **Filters:** Assigned `{"Latrell Dawson"}`; Status `{"In progress"}`.  
- **Notes:** Standalone.  
- **Excel:** `By tech !H4` → `PY(7,...)`.

---

**Page 9 — Python script #9**  
- **Name:** **Yomar Gonzalez** + **In progress**.  
- **Filters:** Assigned `{"Yomar Gonzalez"}`; Status `{"In progress"}`.  
- **Notes:** Standalone.  
- **Excel:** `By tech !N4` → `PY(8,...)`.

---

**Page 10 — Python script #10**  
- **Name:** **Barron Russell** + **In progress**.  
- **Filters:** Assigned `{"Barron Russell"}`; Status `{"In progress"}`.  
- **Notes:** Standalone.  
- **Excel:** `By tech !T4` → `PY(9,...)`.

---

**Page 11 — Python script #11**  
- **Name:** **Antonio Sherfield** + **In progress**.  
- **Filters:** Assigned `{"Antonio Sherfield"}`; Status `{"In progress"}`.  
- **Notes:** Standalone.  
- **Excel:** `By tech !Z4` → `PY(10,...)`.

---

**Page 12 — Python script #12**  
- **Name:** Phase **5** + Unassigned or empty.  
- **Filters:** Phase `{"5"}`; Assigned `{"Unassigned",""}`.  
- **Notes:** Standalone.  
- **Excel:** `unassign!B4` → `PY(11,...)`.

---

**Page 13 — Python script #13**  
- **Name:** Phase **7** + Unassigned or empty.  
- **Filters:** Phase `{"7"}`; Assigned `{"Unassigned",""}`.  
- **Notes:** Standalone.  
- **Excel:** `unassign!H4` → `PY(12,...)`.

---

**Page 14 — Python script #14**  
- **Name:** Phase **8** + Unassigned or empty.  
- **Filters:** Phase `{"8"}`; Assigned `{"Unassigned",""}`.  
- **Notes:** Standalone.  
- **Excel:** `unassign!N4` → `PY(13,...)`.

---

**Page 15 — Python script #15**  
- **Name:** **Latrell Dawson** + **On hold** (no phase).  
- **Filters:** Assigned `{"Latrell Dawson"}`; Status `{"On hold"}`.  
- **Notes:** Standalone.  
- **Excel:** `Phase 5!H5` → `PY(14,...)`.

---

**Page 16 — Python script #16**  
- **Name:** Phase **5** + **Unassigned** only.  
- **Filters:** Assigned `{"Unassigned"}`; Phase `{"5"}`.  
- **Notes:** Standalone.  
- **Excel:** `Phase 5!N5` → `PY(15,...)`.

---

**Page 17 — Python script #17**  
- **Name:** **Yomar Gonzalez** + **On hold**.  
- **Filters:** Assigned `{"Yomar Gonzalez"}`; Status `{"On hold"}`.  
- **Notes:** Standalone.  
- **Excel:** `Phase 5!T5` → `PY(16,...)`.

---

**Page 18 — Python script #18**  
- **Name:** **Barron Russell** + **On hold**.  
- **Filters:** Assigned `{"Barron Russell"}`; Status `{"On hold"}`.  
- **Notes:** Standalone.  
- **Excel:** `Phase 7!H5` → `PY(17,...)`.

---

**Page 19 — Python script #19**  
- **Name:** Phase **7** + **Unassigned** only.  
- **Filters:** Assigned `{"Unassigned"}`; Phase `{"7"}`.  
- **Notes:** Standalone.  
- **Excel:** `Phase 7!N5` → `PY(18,...)`.

---

**Page 20 — Python script #20**  
- **Name:** **Antonio Sherfield** + **On hold**.  
- **Filters:** Assigned `{"Antonio Sherfield"}`; Status `{"On hold"}`.  
- **Notes:** Standalone.  
- **Excel:** `Phase 8!H5` → `PY(19,...)`.

---

**Page 21 — Python script #21**  
- **Name:** Phase **8** + **Unassigned** only.  
- **Filters:** Assigned `{"Unassigned"}`; Phase `{"8"}`.  
- **Notes:** Standalone.  
- **Excel:** `Phase 8!N5` → `PY(20,...)`.

---

# PART 2 — EXCEL FILE ANALYSIS (LAYOUT LAYER)

## Workbook: `Active Service Request Mabi.xlsx`

### 1. All sheets (tabs), in order

1. `ServiceRequest`  
2. `Full_unassign`  
3. `By tech ` *(trailing space in name)*  
4. `unassign`  
5. `Phase 3`  
6. `Phase 4`  
7. `Phase 4c`  
8. `Staff ` *(trailing space)*  
9. `Move ins`

---

### Per-sheet layout

**`ServiceRequest`**  
- **Tables:** **1** Excel table (`SEV_REQUEST` — implied by formulas referencing `SEV_REQUEST[...]`).  
- **Position:** Data from row **2**; row **1** headers: `PH`, `BLD`, `Days open`, `Number`, `Location`, `Created date`, `Due date`, `Service Category`, `Issue`, `Assigned to`, `Priority`, `Status`, `Wo classification`.  
- **Python:** **None** (source data + helper formulas in row 2).  
- **Grouping:** N/A (raw feed).

---

**`Full_unassign`**  
- **Tables:** **5** Python-spill tables **in one horizontal row** (columns **B–F**, **H–L**, **N–R**, **T–X**, **Z–AD**).  
- **Position:** **Top** of sheet; title band **rows 3–4**; **first spill row 5** (anchor cells `B5`, `H5`, `N5`, `T5`, `Z5`).  
- **Section titles (merged cells):**  
  - `B3:F4` → `Full Service request  Report -Mabi Side`  
  - `H3:L4` → `Full Service request  Report Unassigned Mabi`  
  - `N3:R4` → `Unassigned Ph 3`  
  - `T3:X4` → `Unassigned Ph 4`  
  - `Z3:AD4` → `Unassigned Ph 4c`  
- **Grouping structure:** **By report slice** (full phase rollup → global unassigned → three phase-specific unassigned columns).  
- **Python mapping:**  
  - `B5` = script **#1**  
  - `H5` = **#2**  
  - `N5` = **#3**  
  - `T5` = **#4**  
  - `Z5` = **#5**  

---

**`By tech `**  
- **Tables:** **6** Python tables **horizontal**: **B–F**, **H–L**, **N–R**, **T–X**, **Z–AD**, **AF–AJ**.  
- **Titles rows 2–3**; **spill row 4** (`B4`, `H4`, `N4`, `T4`, `Z4`, `AF4`).  
- **Merged titles:**  
  - `B2:F3` → `Mabi`  
  - `H2:L3` → `Dennis Arevalo`  
  - `N2:R3` → `Rayniel Rincon`  
  - `T2:X3` → `Alexander Gonzalez`  
  - `Z2:AD3` → `Diego Zapata`  
  - `AF2:AJ3` → `Victor Castaneda`  
- **Grouping:** **By technician / manager** (first column = manager name `Mabi`, then five named techs).  
- **Python:** `B4` **#6**, `H4` **#7**, `N4` **#8**, `T4` **#9**, `Z4` **#10**, `AF4` **#11**.

---

**`unassign`**  
- **Tables:** **3** horizontal: **B–F**, **H–L**, **N–R**.  
- **Titles rows 2–3**; spills **`B4`, `H4`, `N4`**.  
- **Merged titles:**  
  - `B2:F3` → `Phase 3`  
  - `H2:L3` → `Phase 4`  
  - `N2:R3` → `Phase 4c`  
- **Grouping:** **By phase** (3 / 4 / 4c), each **unassigned** slice.  
- **Python:** `B4` **#3** *(same formula as `Full_unassign!N5`)*, `H4` **#12**, `N4` **#13**.

---

**`Phase 3`**  
- **Tables:** **7** horizontal bands through **AL–AP** (last block).  
- **Titles rows 3–4**; spills from row **5** (`B5`, `H5`, `N5`, `T5`, `Z5`, `AF5`, `AL5`).  
- **Merged titles:**  
  - `B3:F4` & `H3:L4` → `Alexander Gonzalez`  
  - `N3:R4` → `Alexander Gonzalez/Victor Castaneda/Dennis Arevalo`  
  - `T3:X4` & `Z3:AD4` → `Victor Castaneda`  
  - `AF3:AJ4` & `AL3:AP4` → `Dennis Arevalo`  
- **Grouping:** **By technician + status + phase** (In progress / On hold / Unassigned variants for phase 3).  
- **Python:** `B5` **#9**, `H5` **#14**, `N5` **#15**, `T5` **#16**, `Z5` **#17**, `AF5` **#18**, `AL5` **#19**.

---

**`Phase 4`**  
- **Tables:** **7** horizontal (to **AL–AP**).  
- **Merged titles:**  
  - `B3:F4` & `H3:L4` → `Rayniel Rincon`  
  - `N3:R4` → `Rayniel Rincon /Diego Zapata/Dennis Arevalo`  
  - `T3:X4` & `Z3:AD4` → `Diego Zapata`  
  - `AF3:AJ4` & `AL3:AP4` → `Dennis Arevalo`  
- **Grouping:** Same pattern as Phase 3 sheet, for phase **4**.  
- **Python:** `B5` **#8**, `H5` **#20**, `N5` **#21**, `T5` **#22**, `Z5` **#23**, `AF5` **#24**, `AL5` **#25**.

---

**`Phase 4c`**  
- **Tables:** **3** horizontal (**B–F**, **H–L**, **N–R**).  
- **Merged titles:** all three → `Victor Castaneda` (three separate merged blocks).  
- **Python:** `B5` **#26**, `H5` **#27**, `N5` **#28**.

---

**`Staff `**  
- **Tables:** **0** Python tables. **Static** two-column list: header `Staff` / `staff mabi` at `B3`/`E3`, names **B4–B19** and parallel **E4–E19**.  
- **Python:** **None**.

---

**`Move ins`**  
- **Tables:** **1** table referenced as **`Table2`** in formulas (`Table2[[#This Row],[Date ]]` etc.).  
- **Columns:** `Unit`, `Date `, `Days move in ` (row 3).  
- **Python:** **None** (separate from `SEV_REQUEST` Python pipeline).

---

## Workbook: `Active Service Request Robert  .xlsx`

### 1. Sheets in order

1. `ServiceRequest`  
2. `Full_unassign`  
3. `By tech `  
4. `unassign`  
5. `Phase 5`  
6. `Phase 7`  
7. `Phase 8`  
8. `Staff `  

*(No `Move ins` sheet.)*

---

### Per-sheet layout (Robert)

**`ServiceRequest`**  
- **Headers row 1:** `PH` … `Status` — **12** populated headers (two trailing `None` in column 13–14 in the inspected row). **No** `Wo classification` column unlike Mabi.  
- **Python:** **None** (source).

---

**`Full_unassign`**  
- **Tables:** **6** side-by-side (**B–F**, **H–L**, **N–R**, **T–X**, **Z–AD**, **AF–AJ**).  
- **Spill row 5** for first row of each block; data extends **down** many rows (large used range).  
- **Merged titles:**  
  - `B3:F4` → `Full Service request  Report `  
  - `H3:L4` → `Full Service request  Report Unassigned`  
  - `N3:R4` → `Full Service request  Report -Roberto Side`  
  - `T3:X4` → `Full Service request  Report Unassigned Robertos `  
  - `Z3:AD4` → `Full Service request  Report -Mabi Side`  
  - `AF3:AJ4` → `Full Service request  Report Unassigned Mabi`  
- **Python:** `B5` **#1**, `H5` **#2**, `N5` **#3**, `T5` **#4**, `Z5` **#5**, `AF5` **#6**  
- **Grouping:** **Mixed**: two “full report” views, two Roberto-side phase rollups (5/7/8), two “Mabi-side” phase rollups (3/4/4c) — **labels on Z/AF are copied Mabi wording** while logic is Robert scripts **#5** and **#6**.

---

**`By tech `**  
- **Tables:** **5** horizontal (**B–F** through **Z–AD** only — **no AF** column block).  
- **Merged titles:** `Roberto Palacios`, `Latrell Dawson`, `Yomar Gonzalez`, `Barron Russell`, `Antonio Sherfield`.  
- **Spill row 4.**  
- **Python:** `B4` **#7**, `H4` **#8**, `N4` **#9**, `T4` **#10**, `Z4` **#11**.

---

**`unassign`**  
- **Tables:** **3** — titles `Phase 5`, `Phase 7`, `Phase 8`.  
- **Spills `B4`, `H4`, `N4`.**  
- **Python:** **#12**, **#13**, **#14**.

---

**`Phase 5`**  
- **Tables:** **5** horizontal (**B** through **AD**).  
- **Merged titles:** `Latrell Dawson` (×2), `Latrell Dawson/Yomar Gonzalez`, `Yomar Gonzalez` (×2).  
- **Python:** `B5` **#8**, `H5` **#15**, `N5` **#16**, `T5` **#9**, `Z5` **#17**.

---

**`Phase 7`**  
- **Tables:** **3** horizontal.  
- **Merged titles:** `Barron Russell` (×3).  
- **Python:** `B5` **#10**, `H5` **#18**, `N5` **#19**.

---

**`Phase 8`**  
- **Tables:** **3** horizontal.  
- **Merged titles:** `Antonio Sherfield` (×3).  
- **Python:** `B5` **#11**, `H5` **#20**, `N5` **#21**.

---

**`Staff `**  
- **Static** single column of names under `Staff` (`B3` header, **B4–B24**). **No** second “staff mabi” column like Mabi file.  
- **Python:** **None**.

---

### How multiple Python outputs combine on one sheet

- **Single sheet = one dashboard row of section titles + one row of formula anchors.**  
- Each anchor cell holds **one** `PY(k,0,SEV_REQUEST[])`; the spill fills **right** and **down** within that 5-column band.  
- **No** single cell combines two Python outputs — **combination is purely spatial** (side-by-side columns).

---

# PART 3 — STRUCTURE RECONSTRUCTION

## Mabi — full workbook structure

**Sheet 1 — `ServiceRequest`**  
- **Sections:** (none) — header row + data table.  
- **Tables:** `SEV_REQUEST` (raw + formulas).

**Sheet 2 — `Full_unassign`**  
- **Sections:** 5 titled horizontal blocks (see merged titles above).  
- **Tables:** 5 Python spills (scripts **#1–#5**).

**Sheet 3 — `By tech `**  
- **Sections:** 6 titled technician/manager blocks.  
- **Tables:** 6 Python spills (**#6–#11**).

**Sheet 4 — `unassign`**  
- **Sections:** Phase 3 / Phase 4 / Phase 4c.  
- **Tables:** 3 Python spills (**#3**, **#12**, **#13**). **Note:** **#3** is reused from `Full_unassign`.

**Sheet 5 — `Phase 3`**  
- **Sections:** 7 titled blocks (labels repeat technician names; center block title lists three names).  
- **Tables:** 7 Python spills (**#9**, **#14–#19**).

**Sheet 6 — `Phase 4`**  
- **Sections:** 7 titled blocks.  
- **Tables:** 7 Python spills (**#8**, **#20–#25**).

**Sheet 7 — `Phase 4c`**  
- **Sections:** 3 titled blocks (each merged title `Victor Castaneda`).  
- **Tables:** 3 Python spills (**#26–#28**).

**Sheet 8 — `Staff `**  
- **Sections:** One static roster (two columns).  
- **Tables:** 0 Python.

**Sheet 9 — `Move ins`**  
- **Sections:** One operational list.  
- **Tables:** `Table2` (non-Python).

---

## Robert — full workbook structure

**Sheet 1 — `ServiceRequest`**  
- **Sections:** Raw import.  
- **Tables:** `SEV_REQUEST`.

**Sheet 2 — `Full_unassign`**  
- **Sections:** 6 titled horizontal blocks.  
- **Tables:** 6 Python spills (**#1–#6**).

**Sheet 3 — `By tech `**  
- **Sections:** 5 technician blocks.  
- **Tables:** 5 Python spills (**#7–#11**).

**Sheet 4 — `unassign`**  
- **Sections:** Phase 5 / 7 / 8.  
- **Tables:** 3 Python spills (**#12–#14**).

**Sheet 5 — `Phase 5`**  
- **Sections:** 5 blocks (Latrell / Yomar cross-sliced).  
- **Tables:** 5 Python spills (**#8**, **#15**, **#16**, **#9**, **#17**).

**Sheet 6 — `Phase 7`**  
- **Sections:** 3 blocks (Barron-focused).  
- **Tables:** 3 Python spills (**#10**, **#18**, **#19**).

**Sheet 7 — `Phase 8`**  
- **Sections:** 3 blocks (Antonio-focused).  
- **Tables:** 3 Python spills (**#11**, **#20**, **#21**).

**Sheet 8 — `Staff `**  
- **Sections:** Static list.  
- **Tables:** 0 Python.

---

# PART 4 — CRITICAL DETAILS

## 1. Exact ordering of sheets

**Mabi:**  
`ServiceRequest` → `Full_unassign` → `By tech ` → `unassign` → `Phase 3` → `Phase 4` → `Phase 4c` → `Staff ` → `Move ins`

**Robert:**  
`ServiceRequest` → `Full_unassign` → `By tech ` → `unassign` → `Phase 5` → `Phase 7` → `Phase 8` → `Staff `

---

## 2. Exact ordering of sections within sheets

**Mabi `Full_unassign` (left → right):**  
`#1` | `#2` | `#3` | `#4` | `#5`

**Mabi `By tech `:**  
`#6` | `#7` | `#8` | `#9` | `#10` | `#11`

**Mabi `unassign`:**  
`#3` | `#12` | `#13`

**Mabi `Phase 3`:**  
`#9` | `#14` | `#15` | `#16` | `#17` | `#18` | `#19`

**Mabi `Phase 4`:**  
`#8` | `#20` | `#21` | `#22` | `#23` | `#24` | `#25`

**Mabi `Phase 4c`:**  
`#26` | `#27` | `#28`

**Robert `Full_unassign`:**  
`#1` | `#2` | `#3` | `#4` | `#5` | `#6`

**Robert `By tech `:**  
`#7` | `#8` | `#9` | `#10` | `#11`

**Robert `unassign`:**  
`#12` | `#13` | `#14`

**Robert `Phase 5`:**  
`#8` | `#15` | `#16` | `#9` | `#17`

**Robert `Phase 7`:**  
`#10` | `#18` | `#19`

**Robert `Phase 8`:**  
`#11` | `#20` | `#21`

---

## 3. Where duplicates exist

| Duplicate kind | Detail |
|----------------|--------|
| **Same Python script in two cells** | Mabi **#3** appears on **`Full_unassign!N5`** and **`unassign!B4`**. |
| **Duplicate source code** | Mabi **#12 ≡ #4**, **#13 ≡ #5** (identical filter code in `.txt`). |
| **Duplicate technician columns across sheets** | Robert **#8** on `By tech !H4` **and** `Phase 5!B5`; **#9** on `By tech !N4` **and** `Phase 5!T5`; **#10** on `By tech !T4` **and** `Phase 7!B5`; **#11** on `By tech !Z4` **and** `Phase 8!B5`. Same formula id, two placements. |

---

## 4. Where logic is inconsistent (must match for replication)

| Issue | Detail |
|--------|--------|
| **Unassigned semantics** | Scripts **#2** (Mabi/Robert): `== "Unassigned"` only. Other scripts use `["Unassigned",""]` or `"Unassigned"` only with phase — **three different conventions**. |
| **Phase-specific Unassigned** | **#15/#21/#28** (Mabi) and **#16/#19/#21** (Robert): **`Unassigned` only**, no `""`. |
| **Merged titles vs Python** | **Phase 3 `N3:R4`** text lists three names but **#15** is **Unassigned + phase 3**. **Phase 4 `N3:R4`** lists three names but **#21** is **Unassigned + phase 4**. Titles are **not** literal descriptions of the filter. |
| **Robert `Full_unassign` Z / AF labels** | Titles say **“Mabi Side” / “Unassigned Mabi”** but scripts **#5 / #6** are **3/4/4c** rollups — **naming is inconsistent** with Robert’s domain. |

---

## 5. Manual vs systematic

| Element | Manual / arbitrary | Systematic |
|---------|-------------------|------------|
| **Which script attaches to which horizontal band** | **Manual** placement in grid (order of columns per sheet). | Formula pattern `PY(k,0,SEV_REQUEST[])` is systematic. |
| **Merged title text** | **Manual** (includes copy-paste errors and multi-name strings). | Title rows occupy **two rows** (rows 2–3 or 3–4) consistently before spills. |
| **Column width bands** | **Five** letter-columns per table (**B–F**, **H–L**, etc.). | Consistent band width across Python sheets. |
| **`Staff ` sheet** | Entirely **manual** entry. | N/A |
| **`Move ins` (Mabi only)** | Separate **Table2** pipeline. | Not tied to Python index list. |
| **ServiceRequest schema** | Mabi includes **`Wo classification`**; Robert does not (header list differs). | Both use `SEV_REQUEST` name for Python input. |

---

## Required formatting patterns visible from files

- **Title band:** merged ranges **5 columns wide** per table (`B:F`, `H:L`, …).  
- **Title rows:** **two rows** merged vertically for each section title on Python dashboard sheets.  
- **Data anchor:** first Python cell **immediately below** title band — row **4** (`By tech `, `unassign`) or row **5** (`Full_unassign`, `Phase *`).  
- **Horizontal layout:** tables **left-to-right**, **not stacked vertically** on the same sheet (except natural spill downward within each band).  
- **Sheet name trailing spaces:** `By tech ` and `Staff ` include a **trailing space** in Mabi (and `By tech ` / `Staff ` in Robert — verify in UI; file listing shows `By tech ` and `Staff ` with space in Mabi; Robert `Staff ` same pattern).

---

This is the **exact operational structure** recoverable from the four named files: **28** Mabi scripts mapped to **PY(0)–PY(27)** and **21** Robert scripts to **PY(0)–PY(20)**, with **sheet order**, **per-sheet table counts**, **anchor coordinates**, **merged title strings**, and **all filter rules** as in the Python text files.