"""Dashboard chart builder — produces a 3×3 PNG grid of bar charts.

Must import matplotlib and call use("Agg") before any pyplot import to force
the non-interactive backend (safe in headless / Streamlit environments).
"""

from __future__ import annotations

import io
from collections import Counter, defaultdict
from datetime import date
from statistics import mean

import matplotlib
matplotlib.use("Agg")  # must be before pyplot import

import matplotlib.pyplot as plt  # noqa: E402

from domain import turnover_lifecycle as tl
from services.exports.export_service import is_finite_numeric

_VACANT_STATES = {tl.PHASE_VACANT_NOT_READY, tl.PHASE_VACANT_READY}


# ── Bar chart helper ──────────────────────────────────────────────────────────

def _bar(ax, labels: list, values: list, title: str, color: str = "#3b82f6",
         ylabel: str = "Count") -> None:
    if not labels:
        ax.text(0.5, 0.5, "No data", ha="center", va="center",
                transform=ax.transAxes, fontsize=11, color="gray")
        ax.set_title(title)
        ax.axis("off")
        return
    ax.bar(labels, values, color=color, edgecolor="white")
    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=8)
    ax.tick_params(axis="x", rotation=35, labelsize=8)
    ax.tick_params(axis="y", labelsize=8)


# ── Nine chart functions ──────────────────────────────────────────────────────

def _chart_turn_time(ax, rows: list[dict]) -> None:
    buckets = ["0-5", "6-10", "11-15", "16-20", "21+"]
    counts = [0, 0, 0, 0, 0]
    for r in rows:
        dv = r.get("dv")
        if not is_finite_numeric(dv):
            continue
        n = int(dv)
        if n <= 5:
            counts[0] += 1
        elif n <= 10:
            counts[1] += 1
        elif n <= 15:
            counts[2] += 1
        elif n <= 20:
            counts[3] += 1
        else:
            counts[4] += 1
    _bar(ax, buckets, counts, "Turn Time Distribution", color="#3b82f6")


def _chart_units_by_state(ax, rows: list[dict]) -> None:
    counter: Counter = Counter(r.get("operational_state", "—") for r in rows)
    items = sorted(counter.items(), key=lambda x: -x[1])
    labels = [k for k, _ in items]
    values = [v for _, v in items]
    _bar(ax, labels, values, "Units by State", color="#10b981")


def _chart_task_completion(ax, rows: list[dict]) -> None:
    buckets = ["0-25%", "26-50%", "51-75%", "76-100%"]
    counts = [0, 0, 0, 0]
    for r in rows:
        pct = r.get("task_completion_ratio", 0.0) or 0.0
        if pct <= 25:
            counts[0] += 1
        elif pct <= 50:
            counts[1] += 1
        elif pct <= 75:
            counts[2] += 1
        else:
            counts[3] += 1
    _bar(ax, buckets, counts, "Task Completion", color="#f59e0b")


def _chart_sla_by_phase(ax, rows: list[dict]) -> None:
    by_phase: dict[str, int] = defaultdict(int)
    for r in rows:
        if r.get("sla_breach"):
            by_phase[r["phase"]] += 1
    if not by_phase:
        _bar(ax, [], [], "SLA Breaches by Phase", color="#ef4444")
        return
    labels = sorted(by_phase)
    values = [by_phase[p] for p in labels]
    _bar(ax, labels, values, "SLA Breaches by Phase", color="#ef4444")


def _chart_avg_turn_time_by_phase(ax, rows: list[dict]) -> None:
    by_phase: dict[str, list] = defaultdict(list)
    for r in rows:
        dv = r.get("dv")
        if is_finite_numeric(dv):
            by_phase[r["phase"]].append(int(dv))
    if not by_phase:
        _bar(ax, [], [], "Avg Turn Time by Phase", color="#8b5cf6", ylabel="Days")
        return
    labels = sorted(by_phase)
    values = [round(mean(by_phase[p]), 1) for p in labels]
    _bar(ax, labels, values, "Avg Turn Time by Phase", color="#8b5cf6", ylabel="Days")


def _chart_completion_by_phase(ax, rows: list[dict]) -> None:
    by_phase: dict[str, list] = defaultdict(list)
    for r in rows:
        by_phase[r["phase"]].append(r.get("task_completion_ratio", 0.0) or 0.0)
    if not by_phase:
        _bar(ax, [], [], "Completion Rate by Phase", color="#ec4899", ylabel="%")
        return
    labels = sorted(by_phase)
    values = [round(mean(by_phase[p]), 1) for p in labels]
    _bar(ax, labels, values, "Completion Rate by Phase", color="#ec4899", ylabel="%")


def _chart_vacancy_by_phase(ax, rows: list[dict]) -> None:
    by_phase: dict[str, int] = defaultdict(int)
    for r in rows:
        if r["operational_state"] in _VACANT_STATES:
            by_phase[r["phase"]] += 1
    if not by_phase:
        _bar(ax, [], [], "Vacancy by Phase", color="#6366f1")
        return
    labels = sorted(by_phase)
    values = [by_phase[p] for p in labels]
    _bar(ax, labels, values, "Vacancy by Phase", color="#6366f1")


def _chart_units_by_badge(ax, rows: list[dict]) -> None:
    counter: Counter = Counter(r.get("attention_badge", "—") for r in rows)
    items = sorted(counter.items(), key=lambda x: -x[1])
    labels = [k for k, _ in items]
    values = [v for _, v in items]
    _bar(ax, labels, values, "Units by Badge", color="#14b8a6")


def _chart_days_to_movein(ax, rows: list[dict]) -> None:
    buckets = ["0-2", "3-7", "8-14", "15+"]
    counts = [0, 0, 0, 0]
    for r in rows:
        dtm = r.get("days_to_move_in")
        if not is_finite_numeric(dtm) or r.get("move_in_date") is None:
            continue
        n = int(dtm)
        if n <= 2:
            counts[0] += 1
        elif n <= 7:
            counts[1] += 1
        elif n <= 14:
            counts[2] += 1
        else:
            counts[3] += 1
    _bar(ax, buckets, counts, "Days Until Move-In", color="#f97316")


# ── Main entry point ──────────────────────────────────────────────────────────

def build_dashboard_chart(rows: list[dict], today: date) -> bytes:
    """Build a 3×3 bar-chart PNG from export rows. Returns PNG bytes."""
    fig, axes = plt.subplots(3, 3, figsize=(16, 12))
    flat = axes.flatten()

    chart_fns = [
        _chart_turn_time,
        _chart_units_by_state,
        _chart_task_completion,
        _chart_sla_by_phase,
        _chart_avg_turn_time_by_phase,
        _chart_completion_by_phase,
        _chart_vacancy_by_phase,
        _chart_units_by_badge,
        _chart_days_to_movein,
    ]
    for fn, ax in zip(chart_fns, flat):
        fn(ax, rows)

    fig.suptitle("DMRB Portfolio Dashboard", fontsize=14, fontweight="bold")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
