import streamlit as st
from services import task_service
from ui.helpers.formatting import format_date, format_datetime, readiness_badge


def render_task_panel(turnover_id: int) -> None:
    readiness = task_service.get_readiness(turnover_id)

    st.subheader("Tasks")
    st.markdown(readiness_badge(readiness["state"]))
    st.write(f"{readiness['completed']} / {readiness['total']} tasks complete")

    tasks = readiness["tasks"]
    if not tasks:
        st.info("No tasks for this turnover.")
        return

    for task in tasks:
        with st.container(border=True):
            col1, col2, col3, col4, col5, col6 = st.columns([2, 1.2, 1.2, 1.2, 1.2, 1])

            col1.write(task["task_type"])
            col2.write(task["execution_status"])
            col3.write(format_date(task.get("scheduled_date")))
            col4.write(format_date(task.get("vendor_due_date")))
            col5.write(format_datetime(task.get("vendor_completed_at")))

            is_completed = task["execution_status"] == "COMPLETED"

            if not is_completed:
                if col6.button("Complete", key=f"complete_{task['task_id']}"):
                    task_service.complete_task(task["task_id"], actor="manager")
                    st.rerun()
