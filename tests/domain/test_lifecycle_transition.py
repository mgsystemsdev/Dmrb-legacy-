"""Strict lifecycle transition rules (domain.turnover_lifecycle)."""

import pytest

from domain.turnover_lifecycle import (
    PHASE_CANCELED,
    PHASE_CLOSED,
    PHASE_OCCUPIED,
    PHASE_ON_NOTICE,
    PHASE_PRE_NOTICE,
    PHASE_VACANT_NOT_READY,
    PHASE_VACANT_READY,
    TransitionError,
    validate_transition,
)


def test_valid_forward_chain():
    validate_transition(PHASE_PRE_NOTICE, PHASE_ON_NOTICE)
    validate_transition(PHASE_ON_NOTICE, PHASE_VACANT_NOT_READY)
    validate_transition(PHASE_VACANT_NOT_READY, PHASE_VACANT_READY)
    validate_transition(PHASE_VACANT_READY, PHASE_OCCUPIED)
    validate_transition(PHASE_OCCUPIED, PHASE_CLOSED)


def test_cancel_from_early_phases():
    validate_transition(PHASE_PRE_NOTICE, PHASE_CANCELED)
    validate_transition(PHASE_ON_NOTICE, PHASE_CANCELED)
    validate_transition(PHASE_VACANT_NOT_READY, PHASE_CANCELED)
    validate_transition(PHASE_VACANT_READY, PHASE_CANCELED)


def test_close_from_vacant_phases():
    validate_transition(PHASE_VACANT_NOT_READY, PHASE_CLOSED)
    validate_transition(PHASE_VACANT_READY, PHASE_CLOSED)


def test_vacant_ready_back_to_not_ready():
    validate_transition(PHASE_VACANT_READY, PHASE_VACANT_NOT_READY)


def test_invalid_skip_on_notice():
    with pytest.raises(TransitionError, match="not allowed"):
        validate_transition(PHASE_PRE_NOTICE, PHASE_VACANT_NOT_READY)


def test_invalid_occupied_to_canceled():
    with pytest.raises(TransitionError, match="not allowed"):
        validate_transition(PHASE_OCCUPIED, PHASE_CANCELED)


def test_terminal_closed_blocks_all():
    for dest in (
        PHASE_PRE_NOTICE,
        PHASE_ON_NOTICE,
        PHASE_VACANT_NOT_READY,
        PHASE_VACANT_READY,
        PHASE_OCCUPIED,
        PHASE_CLOSED,
        PHASE_CANCELED,
    ):
        with pytest.raises(TransitionError, match="not allowed"):
            validate_transition(PHASE_CLOSED, dest)


def test_terminal_canceled_blocks_all():
    for dest in (
        PHASE_PRE_NOTICE,
        PHASE_ON_NOTICE,
        PHASE_VACANT_NOT_READY,
        PHASE_VACANT_READY,
        PHASE_OCCUPIED,
        PHASE_CLOSED,
        PHASE_CANCELED,
    ):
        with pytest.raises(TransitionError, match="not allowed"):
            validate_transition(PHASE_CANCELED, dest)


def test_unknown_from_phase_rejected():
    with pytest.raises(TransitionError, match="not allowed"):
        validate_transition("NOT_A_PHASE", PHASE_ON_NOTICE)
