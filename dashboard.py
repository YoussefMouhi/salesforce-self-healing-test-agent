"""
dashboard.py -- Streamlit dashboard for the self-healing test agent.

Read-only view over test_runs.db (runs, steps, failures, proposed_fixes).
Actual approval/rejection of proposed fixes stays in review_fixes.py by
design -- this dashboard is for visibility and reporting, not for taking
actions that should go through the deliberate CLI review flow.

Run with: streamlit run dashboard.py
"""

import sqlite3
import pandas as pd
import streamlit as st

DB_PATH = "test_runs.db"


@st.cache_data(ttl=5)
def load_table(query: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()


st.set_page_config(page_title="Self-Healing Test Agent", layout="wide")
st.title("Self-Healing AI Test Automation Agent")
st.caption("Salesforce B2B Commerce storefront -- [redacted] PFA project")

runs_df = load_table("SELECT * FROM runs ORDER BY run_id DESC")
steps_df = load_table("SELECT * FROM steps")
failures_df = load_table("SELECT * FROM failures")
fixes_df = load_table("SELECT * FROM proposed_fixes ORDER BY fix_id DESC")

# --- Top-level summary metrics ------------------------------------------
col1, col2, col3, col4 = st.columns(4)

total_runs = len(runs_df)
pass_runs = (runs_df["overall_status"] == "pass").sum() if total_runs else 0
fail_runs = (runs_df["overall_status"] == "fail").sum() if total_runs else 0
pass_rate = f"{(pass_runs / total_runs * 100):.0f}%" if total_runs else "N/A"

col1.metric("Total runs", total_runs)
col2.metric("Passed", pass_runs)
col3.metric("Failed", fail_runs)
col4.metric("Pass rate", pass_rate)

st.divider()

# --- Run history ----------------------------------------------------------
st.header("Run history")
if runs_df.empty:
    st.info("No runs recorded yet. Run a scenario with orchestrator.py first.")
else:
    display_runs = runs_df[["run_id", "scenario_id", "overall_status", "started_at", "finished_at"]].copy()
    st.dataframe(display_runs, width="stretch", hide_index=True)

    st.subheader("Pass/fail by scenario")
    if not runs_df.empty:
        by_scenario = (
            runs_df.groupby(["scenario_id", "overall_status"])
            .size()
            .unstack(fill_value=0)
        )
        st.bar_chart(by_scenario)

st.divider()

# --- Failure breakdown by classifier category -----------------------------
st.header("Failure breakdown")
if failures_df.empty:
    st.info("No failures recorded yet -- good sign, or no scenarios have run.")
else:
    category_counts = failures_df["category"].value_counts()
    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.write("**By category**")
        st.dataframe(category_counts.rename("count"), width="stretch")
    with col_b:
        st.bar_chart(category_counts)

    st.subheader("Recent failures")
    display_failures = failures_df[
        ["failure_id", "run_id", "step_index", "category", "confidence", "reasoning"]
    ].sort_values("failure_id", ascending=False)
    st.dataframe(display_failures, width="stretch", hide_index=True)

st.divider()

# --- Proposed fixes queue --------------------------------------------------
st.header("Proposed fixes")
st.caption(
    "Read-only view. Approve or reject proposals with `python3 review_fixes.py` "
    "in the terminal -- this dashboard does not take actions on its own."
)

if fixes_df.empty:
    st.info("No proposed fixes yet.")
else:
    status_counts = fixes_df["status"].value_counts()
    cols = st.columns(len(status_counts) if len(status_counts) else 1)
    for i, (status, count) in enumerate(status_counts.items()):
        cols[i].metric(status.capitalize(), count)

    st.subheader("All proposed fixes")
    display_fixes = fixes_df[
        [
            "fix_id", "run_id", "original_target", "proposed_testid_guess",
            "llm_has_confident_match", "status", "classifier_category",
            "classifier_confidence", "created_at", "reviewed_at", "reviewer_note",
        ]
    ]
    st.dataframe(display_fixes, width="stretch", hide_index=True)

    pending_count = (fixes_df["status"] == "pending").sum()
    if pending_count:
        st.warning(f"{pending_count} proposal(s) awaiting human review.")
