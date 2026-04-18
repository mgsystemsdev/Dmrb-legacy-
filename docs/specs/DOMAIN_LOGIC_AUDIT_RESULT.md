# Domain Logic Audit Result

Audit performed per the DMRB Domain Logic Inspection Plan.  
Date: 2026-03-16.

---

## Domain Logic Audit

```
Readiness logic errors: 0
DV calculation errors: 0
DTBR calculation errors: 0
SLA logic errors: 0
Priority engine inconsistencies: 0
QC logic errors: 0
Risk scoring inconsistencies: 0
Vacancy / lifecycle (vacancy_days, effective_move_out, etc.) errors: 0
Import/override/availability classification errors: 0
Move-out absence (should_cancel_turnover) errors: 0
Board metric and flag classification errors: 0
Unit identity (normalize/parse) errors: 0
Mutation safety: PASS
Data consistency (board vs recompute): PASS
Failure detection (invalid states): 0
```

---

## Summary

- **Mutation safety:** All domain modules (readiness, turnover_lifecycle, sla, priority_engine, import_outcomes, move_out_absence, availability_status, manual_override, unit_identity) were scanned. No `db`, `repository`, or `services` imports; only `__future__`, `datetime`/`date`, `re`, and other domain modules. **PASS.**

- **Deterministic tests:** Added or extended tests for readiness (including completion_ratio, Cases 2/6), DV (move-out today = 0), DTBR (overdue → 0, move-in cap), vacancy_days, turnover_window_days, effective_move_out_date, breach_severity, move_in_pressure (3 days), should_cancel_turnover, classify_row_outcome, status_allows_turnover_creation/status_is_vacant, should_apply_import_value, qc_label, _score_board_item (weights and risk_level thresholds), has_any_breach and get_flag_bridge_metrics. All use fixed `today` where applicable. **All passed.**

- **Boundary/edge:** No tasks, move_out None, move_in None, future move-out, all-optional tasks, vendor_due_date None covered; no crashes, deterministic results. **PASS.**

- **Cross-function:** Priority vs readiness and SLA tested (readiness BLOCKED→READY changes priority; SLA BREACH elevates to SLA_RISK). Risk score vs readiness tested. **PASS.**

- **Failure detection:** Priority not NORMAL when SLA BREACH (open turnover). Risk level vs score thresholds (HIGH ≥60, MEDIUM ≥30, LOW <30) asserted. **PASS.**

- **Data consistency:** Script `scripts/domain_data_consistency_check.py` recomputes readiness, DV, DTBR, sla_risk, priority for one board turnover and compares to board output. **PASS.**

- **Board flag fix:** `has_any_breach` was updated to return True for `priority == "MOVE_IN_DANGER"` so it aligns with get_flag_counts and violations.

---

## Test Additions

| Area | File(s) | Additions |
|------|--------|-----------|
| Readiness | tests/domain/test_readiness.py | IN_PROGRESS case (all blocking complete + non-blocking in progress → READY), completion_ratio zero tasks |
| Lifecycle | tests/domain/test_lifecycle.py | DV=0 (move-out today), DTBR overdue→0, DTBR move-in cap, vacancy_days, turnover_window_days, effective_move_out_date |
| SLA | tests/domain/test_sla.py | breach_severity (BREACH→CRITICAL, WARNING→WARNING, OK→INFO), move_in_pressure 3 days |
| Priority | tests/domain/test_priority.py | Cross-function (readiness/SLA), failure detection (not NORMAL when BREACH) |
| Move-out absence | tests/domain/test_move_out_absence.py | New: should_cancel_turnover threshold |
| Import outcomes | tests/domain/test_import_outcomes.py | New: classify_row_outcome branches |
| Availability | tests/domain/test_availability_status.py | New: status_allows_turnover_creation, status_is_vacant |
| Manual override | tests/domain/test_manual_override.py | New: should_apply_import_value (apply, clear_override) |
| Unit identity | tests/domain/test_unit_identity.py | New: normalize_unit_code, parse_unit_parts, compose_identity_key |
| QC | tests/domain/test_qc.py | New: qc_label (QC Done / QC Not Done) |
| Risk score | tests/services/test_risk_service.py | New: _score_board_item weights, risk_level thresholds, cross-function, consistency |
| Board flags | tests/services/test_board_service.py | has_any_breach, get_flag_bridge_metrics with synthetic items |
| Boundaries | tests/domain/test_domain_boundaries.py | New: no tasks, move_out None, move_in None, future move-out, optional-only, vendor_due_date None |

---

## Outcome

Domain logic is **stable and canonical** for the scope of the inspection: all computations covered by the plan pass; mutation safety and data consistency are confirmed; failure-detection assertions are in place.
