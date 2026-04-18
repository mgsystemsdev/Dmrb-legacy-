import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import date
from pathlib import Path


def build_visual_dashboard(
    df: pd.DataFrame,
    output_path: Path,
    total_portfolio: int = 0,
    today: date | None = None,
):
    if today is None:
        today = date.today()

    total_units = total_portfolio if total_portfolio > 0 else len(df)
    df = df.copy()
    df["Phase"] = pd.to_numeric(df["P"], errors="coerce")

    fig = plt.figure(figsize=(16, 12))
    fig.suptitle(
        f"Property Operations Visual Dashboard — {today.strftime('%A, %B %d, %Y')}",
        fontsize=20,
        fontweight="bold",
    )

    # 1 — Turn Time Distribution
    ax1 = plt.subplot(3, 3, 1)
    vacant_df = df[df["Is_Vacant"]]
    aging = vacant_df["Aging_Business_Days"].dropna()
    if len(aging) > 0:
        aging.hist(bins=15, edgecolor="black", alpha=0.7, ax=ax1)
    ax1.axvline(10, color="red", linestyle="--", linewidth=2, label="SLA Limit")
    ax1.set_title("Turn Time Distribution", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Days")
    ax1.set_ylabel("Units")
    ax1.legend(fontsize=8)

    # 2 — Operational State Breakdown
    ax2 = plt.subplot(3, 3, 2)
    state_counts = df["Operational_State"].value_counts()
    colors = ["#2ecc71", "#f39c12", "#e74c3c", "#3498db", "#9b59b6", "#95a5a6", "#1abc9c", "#e67e22"]
    state_counts.plot(kind="bar", ax=ax2, color=colors[: len(state_counts)])
    ax2.set_title("Units by Operational State", fontsize=12, fontweight="bold")
    ax2.set_xlabel("")
    ax2.set_ylabel("Units")
    ax2.tick_params(axis="x", rotation=45)

    # 3 — Task Completion Distribution
    ax3 = plt.subplot(3, 3, 3)
    tc = df["Task_Completion_Ratio"].dropna()
    if len(tc) > 0:
        tc.hist(bins=10, edgecolor="black", alpha=0.7, color="#3498db", ax=ax3)
    ax3.set_title("Task Completion Distribution", fontsize=12, fontweight="bold")
    ax3.set_xlabel("Completion %")
    ax3.set_ylabel("Units")

    # 4 — SLA Compliance by Phase
    ax4 = plt.subplot(3, 3, 4)
    phase_sla = df.groupby("Phase").agg(
        Vacant=("Is_Vacant", "sum"),
        Breaches=("SLA_Breach", "sum"),
    )
    phase_sla["Compliance"] = np.where(
        phase_sla["Vacant"] > 0,
        (phase_sla["Vacant"] - phase_sla["Breaches"]) / phase_sla["Vacant"] * 100,
        100,
    )
    phase_sla["Compliance"].sort_values().plot(kind="barh", ax=ax4, color="#2ecc71")
    ax4.axvline(90, color="red", linestyle="--", linewidth=2, label="90% Target")
    ax4.set_title("SLA Compliance by Phase", fontsize=12, fontweight="bold")
    ax4.set_xlabel("Compliance %")
    ax4.legend(fontsize=8)

    # 5 — Avg Turn Time by Phase
    ax5 = plt.subplot(3, 3, 5)
    phase_turns = df[df["Is_Vacant"]].groupby("Phase")["Aging_Business_Days"].mean().sort_values()
    bar_colors = ["#2ecc71" if x <= 7 else "#f39c12" if x <= 9 else "#e74c3c" for x in phase_turns]
    phase_turns.plot(kind="barh", ax=ax5, color=bar_colors)
    ax5.axvline(10, color="red", linestyle="--", linewidth=2, label="SLA Limit")
    ax5.set_title("Avg Turn Time by Phase", fontsize=12, fontweight="bold")
    ax5.set_xlabel("Days")
    ax5.legend(fontsize=8)

    # 6 — Task Completion Rate
    ax6 = plt.subplot(3, 3, 6)
    task_cols = ["Insp_status", "Paint_status", "MR_Status", "HK_Status", "CC_status"]
    task_done = vacant_df[task_cols].apply(lambda x: x.astype(str).str.upper() == "DONE").sum()
    task_done.index = ["Inspection", "Paint", "MR", "HK", "CC"]
    task_total = len(vacant_df) if len(vacant_df) > 0 else 1
    task_pct = task_done / task_total * 100
    task_pct.plot(kind="bar", ax=ax6, color="#3498db")
    ax6.set_title("Task Completion Rate", fontsize=12, fontweight="bold")
    ax6.set_ylabel("% Complete")
    ax6.set_xlabel("")
    ax6.tick_params(axis="x", rotation=45)

    # 7 — Vacancy Rate by Phase
    ax7 = plt.subplot(3, 3, 7)
    phase_vacancy = df.groupby("Phase").agg(
        Units=("Unit", "count"),
        Vacant=("Is_Vacant", "sum"),
    )
    phase_vacancy["Rate"] = phase_vacancy["Vacant"] / phase_vacancy["Units"] * 100
    phase_vacancy["Rate"].sort_values(ascending=False).plot(kind="barh", ax=ax7, color="#e74c3c")
    ax7.set_title("Vacancy Rate by Phase", fontsize=12, fontweight="bold")
    ax7.set_xlabel("Vacancy %")

    # 8 — Attention Badges
    ax8 = plt.subplot(3, 3, 8)
    import re
    clean_badges = df["Attention_Badge"].apply(
        lambda x: re.sub(r"[^\w\s\-]", "", str(x)).strip() if pd.notna(x) else ""
    )
    badge_counts = clean_badges.value_counts().head(8)
    badge_counts.plot(kind="barh", ax=ax8, color="#9b59b6")
    ax8.set_title("Units by Attention Badge", fontsize=12, fontweight="bold")
    ax8.set_xlabel("Units")

    # 9 — Days to Move-In Distribution
    ax9 = plt.subplot(3, 3, 9)
    movein_df = df[
        df["Is_MoveIn_Present"]
        & (df["Days_To_MoveIn"] >= 0)
        & (df["Days_To_MoveIn"] <= 30)
    ]
    if len(movein_df) > 0:
        movein_df["Days_To_MoveIn"].hist(bins=15, edgecolor="black", alpha=0.7, color="#f39c12", ax=ax9)
        ax9.axvline(2, color="red", linestyle="--", linewidth=2, label="Critical (2 days)")
        ax9.legend(fontsize=8)
    else:
        ax9.text(0.5, 0.5, "No upcoming move-ins", ha="center", va="center", fontsize=12)
    ax9.set_title("Days Until Scheduled Move-In", fontsize=12, fontweight="bold")
    ax9.set_xlabel("Days")
    ax9.set_ylabel("Units")

    plt.tight_layout(rect=[0, 0, 1, 0.95])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)

    return output_path
