
import os
import sys
from datetime import date

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import task_service
from db.repository import task_repository
from services.task_service import (
    STATUS_SCHEDULED, STATUS_IN_PROGRESS, STATUS_COMPLETE, 
    STATUS_BLOCKED, STATUS_SKIPPED, TaskError
)

def test_fsm():
    # Setup: need a property and turnover.
    property_id = 2
    turnover_id = 2
    
    print("--- Starting Task FSM Verification ---")
    
    # Create a task for testing
    task_type = "FSM_TEST_TASK"
    try:
        # Clean up existing test task if any
        existing = task_repository.get_by_turnover(turnover_id)
        for t in existing:
            if t["task_type"] == task_type:
                # We don't have a delete_task in repo, so we just use it
                task_id = t["task_id"]
                # Reset to SCHEDULED directly via repo to avoid service validation
                task_repository.update(task_id, execution_status=STATUS_SCHEDULED, skip_allowed=False, blocked_reason=None)
                break
        else:
            task = task_service.create_task(property_id, turnover_id, task_type)
            task_id = task["task_id"]
    except Exception as e:
        print(f"Setup failed: {e}")
        return

    print(f"Task created with ID {task_id}, initial status: {STATUS_SCHEDULED}")

    # Helper to check transition
    def try_transition(new_status, reason=None, expected_fail=False):
        try:
            task_service.update_task(task_id, execution_status=new_status, blocked_reason=reason)
            if expected_fail:
                print(f"❌ ERROR: Transition to {new_status} succeeded but was expected to fail.")
            else:
                print(f"✅ SUCCESS: Transition to {new_status} succeeded.")
        except TaskError as e:
            if expected_fail:
                print(f"✅ EXPECTED FAIL: Transition to {new_status} failed with: {e}")
            else:
                print(f"❌ ERROR: Transition to {new_status} failed: {e}")

    # 1. Valid: SCHEDULED -> IN_PROGRESS
    try_transition(STATUS_IN_PROGRESS)

    # 2. Invalid: IN_PROGRESS -> SCHEDULED (not in allowed list)
    try_transition(STATUS_SCHEDULED, expected_fail=True)

    # 3. Valid: IN_PROGRESS -> BLOCKED (with reason)
    try_transition(STATUS_BLOCKED, reason="Waiting for materials")

    # 4. Invalid: IN_PROGRESS -> BLOCKED (without reason)
    # First move back to IN_PROGRESS and clear reason
    task_service.update_task(task_id, execution_status=STATUS_IN_PROGRESS, blocked_reason=None)
    try_transition(STATUS_BLOCKED, reason=None, expected_fail=True)

    # 5. Valid: BLOCKED -> IN_PROGRESS
    # Re-block first
    task_service.update_task(task_id, execution_status=STATUS_BLOCKED, blocked_reason="Test")
    try_transition(STATUS_IN_PROGRESS)

    # 6. Invalid: IN_PROGRESS -> SKIPPED (when skip_allowed=False)
    try_transition(STATUS_SKIPPED, expected_fail=True)

    # 7. Valid: IN_PROGRESS -> SKIPPED (when skip_allowed=True)
    task_repository.update(task_id, skip_allowed=True)
    try_transition(STATUS_SKIPPED)

    # 8. Terminal: SKIPPED -> IN_PROGRESS (Terminal state, no transitions out defined)
    try_transition(STATUS_IN_PROGRESS, expected_fail=True)

    print("--- Verification Finished ---")

if __name__ == "__main__":
    test_fsm()
