# Operational Priority Engine Specification

Last updated: 2026-03-15
Status: Reflects current `domain.priority_engine` behavior

## 1. Purpose

This document describes how the current code assigns board priority to open turnovers.

The active implementation lives in:

- `domain.priority_engine.py`
- `domain.sla.py`
- `domain.readiness.py`
- `domain.turnover_lifecycle.py`

## 2. Current Priority Levels

Highest to lowest:

1. `MOVE_IN_DANGER`
2. `SLA_RISK`
3. `INSPECTION_DELAY`
4. `NORMAL`
5. `LOW`

## 3. Current Evaluation Order

The first matching rule wins.

### Priority 1: `MOVE_IN_DANGER`

Current rule:

- move-in date exists
- move-in is within 3 days or already overdue
- readiness is not `READY`

This threshold is currently 3 days in code, not 5.

### Priority 2: `SLA_RISK`

Current rule:

- `sla.sla_risk()` returns `WARNING` or `BREACH`

Current SLA settings in code:

- threshold: 14 days
- warning threshold: 75% of 14 days

This means older docs that describe a 10-day SLA are not current-state accurate for the running priority engine.

### Priority 3: `INSPECTION_DELAY`

Current rule:

- readiness state is `BLOCKED`

Important note:

- the current code does not explicitly model a 24-48 hour inspection SLA
- "inspection delay" is effectively inferred from blocking readiness state, not from a dedicated inspection timestamp rule

### Priority 4: `NORMAL`

Current rule:

- the turnover is active
- it is not already classified as higher risk
- it is not low-attention

### Priority 5: `LOW`

Current rule:

- turnover is closed or canceled, or
- turnover is vacant ready and readiness is `READY`, or
- turnover is pre-notice / on-notice with no active urgency

## 4. Inputs Used by the Engine

The priority engine currently depends on:

- lifecycle phase
- readiness state
- days to move-in
- SLA risk level

It does not currently use:

- explicit QC completion rules
- a separate inspection timestamp model
- persisted board-priority values

## 5. Examples

### Example A

- move-in in 2 days
- tasks incomplete

Result:

- `MOVE_IN_DANGER`

### Example B

- move-out 11 days ago
- no move-in scheduled
- turnover still open

Result:

- likely `SLA_RISK` because the 14-day threshold is approaching

### Example C

- blocking tasks incomplete
- no immediate move-in pressure
- no SLA warning yet

Result:

- `INSPECTION_DELAY`

### Example D

- vacant ready
- required tasks complete

Result:

- `LOW`
