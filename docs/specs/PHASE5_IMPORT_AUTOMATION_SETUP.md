# Phase 5 — Import Automation Layer: Setup Guide

This guide covers applying the automation and running it going forward.

---

## One-time setup (catch up)

### Step 1 — Apply the database migration

The `unit_on_notice_snapshot` table must exist before the import can store On Notice units for automation.

- **If the app runs with bootstrap:** `ensure_database_ready()` applies migration 010 when the app starts and the table is missing. Restart the app or load a page that triggers DB init so the table is created.
- **If you apply migrations manually:** Run `db/migrations/010_unit_on_notice_snapshot.sql` against your database.

### Step 2 — Re-import Available Units

After the migration, run one Available Units import (Import Reports → Available Units → upload your latest CSV and run import). The snapshot table is only populated when the import runs and encounters On Notice units with no turnover. That import will write those rows into the snapshot.

### Step 3 — Run the automation once (catch up)

Process any snapshot rows and existing On Notice turnovers whose available date has already passed:

- **From the UI:** Import Reports → Available Units tab → click **"Run automation now (catch up)"**. This runs the same logic as the midnight script and shows how many turnovers were transitioned and created.
- **From the command line:**  
  `python3 scripts/run_midnight_automation.py`  
  (requires `DATABASE_URL` in the environment or `.streamlit/secrets.toml`.)

Then check the board — units that were On Notice with past available dates should appear as active turnovers (Vacant Not Ready).

### Step 4 — Schedule the daily run

For ongoing automation, run the midnight script once per day (e.g. after midnight):

```bash
# Example: run at 00:05 every day (set DATABASE_URL and path for your environment)
5 0 * * * cd /path/to/DRMB_PROD && DATABASE_URL='...' python3 scripts/run_midnight_automation.py
```

Or use your platform’s scheduler (systemd timer, cloud scheduler, etc.) to invoke the same script with the same `DATABASE_URL` as the app.

---

## Summary

| Step | Action |
|------|--------|
| 1 | Ensure migration 010 is applied (table `unit_on_notice_snapshot` exists). |
| 2 | Re-import the latest Available Units CSV. |
| 3 | Run automation once (UI button or `scripts/run_midnight_automation.py`). |
| 4 | Schedule the script daily (cron or equivalent). |

After that, the system will transition On Notice → Vacant Not Ready and create turnovers from the snapshot automatically each day.
