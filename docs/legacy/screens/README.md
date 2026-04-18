# UI Skeleton Pages

One skeleton per screen, built from [UI_BLUEPRINT.md](../UI_BLUEPRINT.md). Layout and structure only; placeholder data, no backend.

**Run a skeleton standalone:**

```bash
streamlit run docs/skeleton_pages/sidebar.py
streamlit run docs/skeleton_pages/page_01_morning_workflow.py
streamlit run docs/skeleton_pages/page_02_dmrb_board.py
streamlit run docs/skeleton_pages/page_03_flag_bridge.py
streamlit run docs/skeleton_pages/page_04_risk_radar.py
streamlit run docs/skeleton_pages/page_05_report_operations.py
streamlit run docs/skeleton_pages/page_06_turnover_detail.py
streamlit run docs/skeleton_pages/page_07_ai_agent.py
streamlit run docs/skeleton_pages/page_08_admin.py
```

- **Sidebar:** `sidebar.py` — Left rail: title, caption, Navigate radio (8 pages), Top Flags expanders with unit buttons
- **Page 1:** `page_01_morning_workflow.py` — Morning Workflow (title, 4 sections, import status, repair queue, risk summary, today’s critical)
- **Page 2:** `page_02_dmrb_board.py` — DMRB Board (filter bar, metrics bar, Unit Info / Unit Tasks tabs with data editors)
- **Page 3:** `page_03_flag_bridge.py` — Flag Bridge (filter row, metrics row, read-only breach table)
- **Page 4:** `page_04_risk_radar.py` — Risk Radar (Phase / Risk Level / search filters, 4 metrics, risk table)
- **Page 5:** `page_05_report_operations.py` — Report Operations (3 tabs: Missing Move-Out, FAS Tracker, Import Diagnostics)
- **Page 6:** `page_06_turnover_detail.py` — Turnover Detail (unit lookup or full detail: Unit info, Status, Dates, W/D, Risks, Authority expander, Tasks, Notes)
- **Page 7:** `page_07_ai_agent.py` — DMRB AI Agent (sessions list left, suggestions or chat messages right, chat input)
- **Page 8:** `page_08_admin.py` — Admin (control bar, 5 tabs: Add Unit, Import, Unit Master Import, Exports, Dropdown Manager; property structure)
