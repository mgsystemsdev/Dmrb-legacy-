# Data Flow Diagram

This diagram illustrates the real-world movement of data through the DMRB system, highlighting the tension between external PMS reports and manual operational overrides, as well as the "Write-on-Read" side effects triggered by the UI.

```mermaid
flowchart TD

%% --- Layers ---
subgraph External
    PMS[PMS Report Files: CSV/Excel]
end

subgraph UI
    Console[Import Console]
    Board[DMRB Board / Morning Workflow]
    Detail[Unit Detail View]
end

subgraph Services
    Orch[Import Orchestrator]
    MO_Svc[Move Outs Service]
    AU_Svc[Available Units Service]
    TO_Svc[Turnover Service]
    Risk_Svc[Risk & SLA Service]
end

subgraph Domain
    Rules[Override & Reconciliation Rules]
    Life[Lifecycle Phase Engine]
end

subgraph Database
    DB_TO[(turnover Table)]
    DB_Row[(import_row Table)]
    DB_Audit[(audit_log Table)]
    DB_Snap[(unit_on_notice_snapshot Table)]
end

%% --- Flow (top-down only) ---

%% Ingestion Flow
PMS -- "Upload file (bytes)" --> Console
Console -- "Request import (report_type, file)" --> Orch
Orch -- "1. Compute checksum [implicit]" --> DB_Row
Orch -- "2. Parse & Resolve Unit [implicit]" --> Rules

%% Move Outs specific flow
Rules -- "3. RECONCILE (incoming vs manual_override_at)" --> MO_Svc
MO_Svc -- "WRITE (update dates or missing_count)" --> DB_TO
MO_Svc -- "WRITE (audit entries)" --> DB_Audit

%% Available Units specific flow
Rules -- "3. RECONCILE (incoming vs manual_override_at)" --> AU_Svc
AU_Svc -- "WRITE (update readiness/status)" --> DB_TO
AU_Svc -- "WRITE (missing unit logic)" --> DB_TO
AU_Svc -- "WRITE (snapshot for future automation)" --> DB_Snap

%% Write-on-Read Side Effect
Board -- "Trigger: [implicit] ensure_on_notice_turnovers" --> TO_Svc
TO_Svc -- "4. READ (latest AU batch rows)" --> DB_Row
TO_Svc -- "5. WRITE (Create missing turnovers)" --> DB_TO
TO_Svc -- "6. WRITE (Auto-instantiate tasks)" --> DB_Audit

%% State Derivation (Read Flow)
Board -- "Request Board View" --> TO_Svc
TO_Svc -- "READ (raw facts)" --> DB_TO
TO_Svc -- "7. CALCULATE (derived phase/priority)" --> Life
Life -- "Display derived state" --> Board

%% Manual Overrides
Detail -- "Manual Update (e.g., confirmed_date)" --> TO_Svc
TO_Svc -- "8. WRITE (Set manual_override_at timestamp)" --> DB_TO
TO_Svc -- "9. RECALCULATE (SLA/Risk)" --> Risk_Svc
Risk_Svc -- "WRITE (Update risk markers)" --> DB_TO
```
