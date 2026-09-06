"""
pages/1_Live_Demo.py -- Live Demo page for the Streamlit dashboard.

Write a user story, generate a Playwright scenario with the LLM, then run
it against the live org -- no terminal needed. Appears as its own page in
the sidebar automatically (Streamlit's multipage convention).
"""

import asyncio
import json
import subprocess
import sqlite3

import streamlit as st

from generator import generate_scenario, save_scenario
from orchestrator import run_scenario
from healer import classify_failure

DB_PATH = "test_runs.db"

st.set_page_config(page_title="Live Demo", layout="wide")
st.title("Self-Healing AI Test Automation Agent")
st.caption("Salesforce B2B Commerce storefront -- PFA project")

st.header("1. Generate a scenario from a user story")

with st.expander("Or load an existing scenario file (for demos)"):
    override_path = st.text_input(
        "Scenario file path",
        placeholder="scenarios/live_demo_break_2.json",
        key="live_demo_override_path",
    )
    if st.button("Load This File"):
        import json
        try:
            with open(override_path) as f:
                scenario = json.load(f)
            st.session_state["live_demo_scenario"] = scenario
            st.session_state["live_demo_scenario_path"] = override_path
            st.session_state.pop("live_demo_result", None)
            st.success(f"Loaded {override_path}")
        except Exception as e:
            st.error(f"Could not load file: {e}")

user_story = st.text_area(
    "User story",
    placeholder="As a buyer, I want to add 3 units of Diesel Fuel - 55 Gallon Drum to my cart and check out.",
    key="live_demo_story",
)

if st.button("Generate Scenario"):
    if not user_story.strip():
        st.warning("Enter a user story first.")
    else:
        with st.spinner("Generating scenario with the LLM..."):
            try:
                scenario = generate_scenario(user_story)
                scenario_path = save_scenario(scenario)
                st.session_state["live_demo_scenario"] = scenario
                st.session_state["live_demo_scenario_path"] = scenario_path
                st.session_state.pop("live_demo_result", None)
                st.session_state.pop("order_approval_status", None)
            except Exception as e:
                st.error(f"Generation failed: {e}")

if "live_demo_scenario" in st.session_state:
    st.success(f"Saved to {st.session_state['live_demo_scenario_path']}")
    st.json(st.session_state["live_demo_scenario"])

    st.header("2. Run it against the live org")

    if st.button("Run Scenario"):
        with st.spinner("Running scenario -- this drives a real browser session, may take a while..."):
            try:
                record = asyncio.run(
                    run_scenario(st.session_state["live_demo_scenario_path"])
                )
                st.session_state["live_demo_result"] = record
            except Exception as e:
                st.error(f"Run failed: {e}")

if "live_demo_result" in st.session_state:
    result = st.session_state["live_demo_result"]
    status = str(result.get("overall_status", "unknown"))

    if status == "pass":
        st.success(f"Overall result: {status.upper()}")
    else:
        st.error(f"Overall result: {status.upper()}")

    for step in result.get("steps", []):
        idx = step.get("step_index")
        action = step.get("action", "")
        target = step.get("target", "")
        step_status = step.get("status", "").upper()
        detail = step.get("detail", "")
        icon = "PASS" if step.get("status") == "pass" else "FAIL"
        st.markdown(f"**[{idx}] {icon}** {action} `{target}` \u2014 {detail}")

    failed_steps = [s for s in result.get("steps", []) if s.get("status") == "fail"]

    if failed_steps:
        st.header("3. Self-healing: what the system found")

        failed_step = failed_steps[0]
        classification = classify_failure(failed_step)

        st.subheader("Failure classification")
        st.markdown(
            f"**Category:** {classification['category']} | "
            f"**Confidence:** {classification['confidence']}"
        )
        st.markdown(f"**Reasoning:** {classification['reasoning']}")

        if classification["category"] == "SELECTOR_NOT_FOUND":
            conn = sqlite3.connect(DB_PATH)
            try:
                row = conn.execute(
                    "SELECT run_id FROM runs WHERE scenario_id = ? "
                    "ORDER BY run_id DESC LIMIT 1",
                    (result.get("scenario_id"),),
                ).fetchone()
                run_id = row[0] if row else None

                proposal = None
                if run_id is not None:
                    proposal = conn.execute(
                        "SELECT fix_id, original_target, proposed_testid_guess, "
                        "llm_has_confident_match, llm_reasoning, status "
                        "FROM proposed_fixes WHERE run_id = ? AND step_index = ?",
                        (run_id, failed_step.get("step_index")),
                    ).fetchone()
            finally:
                conn.close()

            if proposal:
                fix_id, original, proposed, confident, reasoning, fix_status = proposal
                st.markdown(f"**Original (failed) target:** `{original}`")
                st.markdown(f"**Proposed replacement:** `{proposed}`")
                st.markdown(f"**LLM has confident match:** {bool(confident)}")
                st.markdown(f"**LLM reasoning:** {reasoning}")
                st.markdown(f"**Status:** {fix_status} (fix_id={fix_id})")
            else:
                st.info("No self-healing proposal was generated for this failure category.")
        else:
            st.info("No self-healing proposal was generated for this failure category.")

    submitted_checkout = any(
        s.get("target") == "checkout-submit-button" and s.get("status") == "pass"
        for s in result.get("steps", [])
    )

    if status == "pass" and submitted_checkout:
        try:
            proc = subprocess.run(
                [
                    "sf", "data", "query", "--json", "--query",
                    "SELECT Id, TotalAmount, Approval_Required__c FROM Order "
                    "ORDER BY CreatedDate DESC LIMIT 1",
                ],
                capture_output=True, text=True, timeout=30,
            )
            records = json.loads(proc.stdout).get("result", {}).get("records", [])
            latest_order = records[0] if records else None
        except Exception as e:
            latest_order = None
            st.warning(f"Could not check order approval status: {e}")

        if latest_order and latest_order.get("Approval_Required__c"):
            st.header("4. Order approval required")
            order_id = latest_order.get("Id")
            total = latest_order.get("TotalAmount")

            if "order_approval_status" not in st.session_state:
                st.session_state["order_approval_status"] = "draft"

            if st.session_state["order_approval_status"] == "draft":
                st.warning(
                    f"This order (**{order_id}**, total **${total:,.2f}**) exceeds "
                    f"the $10,000 threshold and requires manager approval before "
                    f"it can be finalized."
                )
                email_body = (
                    f"Subject: Approval needed -- Order {order_id}\n\n"
                    f"An order totaling ${total:,.2f} has been submitted and "
                    f"requires your approval.\n\n"
                    f"Order ID: {order_id}\n"
                    f"Total: ${total:,.2f}\n\n"
                    f"Please review and approve or reject this order."
                )
                st.text_area("Generated approval email", email_body, height=180, disabled=True)
                if st.button("Send Approval Request"):
                    st.session_state["order_approval_status"] = "sent"
                    st.rerun()

            elif st.session_state["order_approval_status"] == "sent":
                st.info(f"Approval email sent. Waiting for manager decision on order **{order_id}**...")
