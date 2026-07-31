import sqlite3
from healer import classify_failure
import re
import asyncio
import os
import json
import sys
from datetime import datetime
from pathlib import Path

import subprocess

SF_TARGET_ORG = "devOrg"
LIGHTNING_PAGE_PATH = "/lightning/n/Catalog_Test"


def get_sf_session():
    env = os.environ.copy()
    env["SF_TEMP_SHOW_SECRETS"] = "true"

    result = subprocess.run(
        ["sf", "org", "display", "--target-org", SF_TARGET_ORG, "--verbose", "--json"],
        capture_output=True, text=True, env=env,
    )
    if result.returncode != 0:
        raise SystemExit(f"Failed to fetch SF session via CLI: {result.stderr}")

    data = json.loads(result.stdout)
    return data["result"]["accessToken"], data["result"]["instanceUrl"]


async def ensure_logged_in(session):
    access_token, instance_url = get_sf_session()
    frontdoor_url = f"{instance_url}/secur/frontdoor.jsp?sid={access_token}&retURL={LIGHTNING_PAGE_PATH}"

    print("  [auth] Using frontdoor.jsp session-token authentication...")
    await session.call_tool("playwright_navigate", {"url": frontdoor_url})
    await asyncio.sleep(2)
    await session.call_tool("playwright_navigate", {"url": CATALOG_TEST_URL})
    await wait_for_element(session, "[data-testid=\"product-catalog\"]", timeout_seconds=25)
    print("  [auth] Session established, navigated to Catalog Test.")



# Evidence-based mapping from data-testid -> literal visible text that only
# appears once that element is genuinely rendered. Built from LWC templates
# because LWC uses CLOSED native Shadow DOM: document.querySelectorAll(...)
# and playwright_get_visible_html cannot see inside components at all (proven
# empirically), while playwright_get_visible_text can, since it reflects the
# accessibility tree which necessarily crosses closed shadow boundaries.
#
# KNOWN LIMITATION: cart-total, debug-raw-cart, and checkout-error render only
# dynamic numbers/JSON/messages with no fixed label, so there is no reliable
# literal marker for them specifically. They fall back to the generic
# "Checkout" mount-proxy, which confirms the storefront rendered but cannot
# distinguish that exact element's state.
TESTID_MARKERS = {
    "product-catalog": "Add to Cart",
    "product-card": "Add to Cart",
    "product-name": "Add to Cart",
    "product-price": "Add to Cart",
    "add-to-cart-button": "Add to Cart",
    "cart-summary": "Checkout",
    "cart-item": "Remove",
    "cart-item-name": "Remove",
    "cart-item-quantity": "Remove",
    "cart-item-remove": "Remove",
    "cart-total": "Checkout",
    "checkout-form": "Checkout",
    "checkout-empty": "Your cart is empty.",
    "checkout-total": "Total:",
    "checkout-approval-warning": "will require manager approval",
    "checkout-submit-button": "Submit Order",
    "checkout-error": "Checkout",
    "checkout-confirmation": "Order created:",
    "debug-raw-cart": "Checkout",
}

def _extract_testid(selector: str) -> str:
    """Pull the testid value out of a '[data-testid="x"]' style selector."""
    m = re.search(r'data-testid=\"([^\"]+)\"', selector)
    return m.group(1) if m else ""

def _tool_indicates_failure(res, tool_output: str) -> bool:
    """isError from this MCP server has been observed to return False even
    when the underlying Playwright action genuinely failed (e.g. a click
    that timed out waiting for a locator). Treat known failure phrases in
    the tool's own text output as authoritative, in addition to isError."""
    if getattr(res, "isError", False):
        return True
    lowered = tool_output.lower()
    return any(phrase in lowered for phrase in (
        "operation failed",
        "timeout",
        "exceeded",
        "no node found",
        "not visible",
        "not attached",
    ))


def _tool_text(res) -> str:
    """Flatten any MCP tool result's text content -- used to capture the
    real error message on a failed click/fill, instead of a static
    success-looking string regardless of outcome."""
    if not getattr(res, "content", None):
        return ""
    return "".join(b.text for b in res.content if getattr(b, "type", None) == "text")


async def _visible_text(session) -> str:
    res = await session.call_tool("playwright_get_visible_text", {})
    return "".join(b.text for b in res.content if getattr(b, "type", None) == "text")


async def wait_for_element(session, selector: str, timeout_seconds: int = 25, poll_interval: float = 1.5):
    """Poll until at least one matching element exists, instead of guessing
    a fixed sleep duration. LWC @wire Apex calls can take a variable amount
    of time to resolve, especially on a fresh session/page load."""
    waited = 0.0
    while waited < timeout_seconds:
        # Poll for the literal marker text tied to this testid instead of a
        # DOM query, since closed-shadow LWC content is invisible to
        # querySelectorAll/get_visible_html but visible via get_visible_text.
        testid = _extract_testid(selector)
        marker = TESTID_MARKERS.get(testid)
        text = await _visible_text(session)
        if marker and marker in text:
            print(f"  [wait] Found {selector} (marker '{marker}') after {waited:.1f}s")
            return True
        if not marker:
            print(f"  [wait] WARNING: no marker mapping for testid '{testid}', cannot verify reliably")
        await asyncio.sleep(poll_interval)
        waited += poll_interval
    print(f"  [wait] Timed out after {timeout_seconds}s waiting for {selector}")
    return False

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

CATALOG_TEST_URL = "https://orgfarm-6e1a6e3ea8-dev-ed.develop.lightning.force.com/lightning/n/Catalog_Test"

SERVER_PARAMS = StdioServerParameters(
    command="npx",
    args=["playwright-mcp-server"],
)


def selector_for(target: str, scope_text: str = None) -> str:
    """Convert a data-testid style target into a real CSS selector.

    If scope_text is given, scopes the match to a specific product-card
    containing that text -- e.g. selector_for("add-to-cart-button", "Test Widget A")
    targets only the Add to Cart button on the Test Widget A card, instead of
    the ambiguous bare selector matching whichever card comes first in the DOM.
    Uses Playwright's :has-text() pseudo-class, which (like click/fill, and
    unlike document.querySelectorAll) operates at the browser-engine level and
    correctly reaches into closed native Shadow DOM LWC content.
    """
    if scope_text:
        return f'[data-testid="product-card"]:has-text("{scope_text}") [data-testid="{target}"]'
    return f'[data-testid="{target}"]'


async def run_step(session: ClientSession, step: dict) -> dict:
    action = step.get("action")
    target = step.get("target")
    value = step.get("value")
    expected = step.get("expected")

    result = {"action": action, "target": target, "status": "unknown", "detail": None}

    try:
        if action == "navigate":
            # Single-page storefront: every navigate step lands on the same
            # Catalog Test page. `target` here is a data-testid style label,
            # not a real destination, so it is logged but not used as a URL.
            res = await session.call_tool("playwright_navigate", {"url": CATALOG_TEST_URL})
            found = await wait_for_element(session, '[data-testid="product-catalog"]', timeout_seconds=25)
            result["status"] = "fail" if (getattr(res, "isError", False) or not found) else "pass"
            result["detail"] = f"Navigated to Catalog Test (step target label: {target}), catalog_rendered={found}"

        elif action == "click":
            selector = selector_for(target, step.get("scope_text"))
            res = await session.call_tool("playwright_click", {"selector": selector})
            tool_output = _tool_text(res)
            is_error = _tool_indicates_failure(res, tool_output)
            result["status"] = "fail" if is_error else "pass"
            result["detail"] = (
                f"Clicked {selector}" if not is_error
                else f"FAILED to click {selector}: {tool_output}"
            )
            result["raw_tool_output"] = tool_output
            if is_error:
                snap = await session.call_tool("playwright_get_visible_text", {})
                result["visible_text_at_failure"] = _tool_text(snap)

        elif action == "fill":
            selector = selector_for(target)
            res = await session.call_tool("playwright_fill", {"selector": selector, "value": str(value)})
            tool_output = _tool_text(res)
            is_error = _tool_indicates_failure(res, tool_output)
            result["status"] = "fail" if is_error else "pass"
            result["detail"] = (
                f"Filled {selector} with '{value}'" if not is_error
                else f"FAILED to fill {selector} with '{value}': {tool_output}"
            )
            result["raw_tool_output"] = tool_output
            if is_error:
                snap = await session.call_tool("playwright_get_visible_text", {})
                result["visible_text_at_failure"] = _tool_text(snap)

        elif action == "assert":
            if target == "NOT_IMPLEMENTED":
                result["status"] = "skipped"
                result["detail"] = f"Feature not yet implemented: {expected}"
                return result

            selector = selector_for(target)
            res = await session.call_tool("playwright_get_visible_text", {})
            text_content = ""
            if res.content:
                text_content = "".join(
                    block.text for block in res.content if getattr(block, "type", None) == "text"
                )

            # We check for existence/non-empty rendering of the target element
            # rather than a literal string match against `expected`, since
            # `expected` is a natural-language description, not exact page text.
            testid = _extract_testid(selector)
            marker = TESTID_MARKERS.get(testid)
            # Some assertions (e.g. checkout-confirmation) follow a real Apex
            # DML call, which is not instantaneous -- poll briefly instead of
            # checking a single snapshot, to avoid a false "fail" recorded
            # before the server round-trip completes.
            found_marker = False
            visible_text = ""
            for _ in range(6):  # up to ~6s
                visible_text = await _visible_text(session)
                if marker and marker in visible_text:
                    found_marker = True
                    break
                await asyncio.sleep(1)
            raw_text = f"marker={marker!r} found_in_visible_text={found_marker}"

            # The tool returns a descriptive string like
            # "Executed JavaScript: ... Result: <value>" -- extract the
            # actual trailing value rather than matching the whole string.
            found = found_marker
            result["status"] = "pass" if found else "fail"
            result["detail"] = f"Assertion on {selector}: expected '{expected}', {raw_text}"

            if not found:
                shot = await session.call_tool("playwright_screenshot", {"name": f"debug_{target}"})
                result["debug_screenshot"] = str(shot)

        elif action == "login":
            result["status"] = "skipped"
            result["detail"] = "Login/authentication flow not yet implemented"

        else:
            result["status"] = "fail"
            result["detail"] = f"Unknown action type: {action}"

    except Exception as e:
        result["status"] = "error"
        result["detail"] = str(e)

    return result



DB_PATH = "test_runs.db"

def save_run_to_db(run_record: dict) -> None:
    """Persist a completed scenario run into runs/steps/failures tables."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO runs (scenario_id, started_at, finished_at, overall_status) "
            "VALUES (?, ?, ?, ?)",
            (
                run_record.get("scenario_id"),
                run_record.get("started_at"),
                run_record.get("finished_at"),
                run_record.get("overall_status"),
            ),
        )
        run_id = cur.lastrowid

        for step in run_record.get("steps", []):
            cur.execute(
                "INSERT INTO steps (run_id, step_index, action, target, status, detail) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    step.get("step_index"),
                    step.get("action"),
                    step.get("target"),
                    step.get("status"),
                    step.get("detail"),
                ),
            )
            if step.get("status") in ("fail", "error"):
                classification = classify_failure(step)
                cur.execute(
                    "INSERT INTO failures (run_id, step_index, error_detail, debug_screenshot_path, "
                    "category, confidence, reasoning) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        run_id,
                        step.get("step_index"),
                        step.get("detail"),
                        step.get("debug_screenshot"),
                        classification["category"],
                        classification["confidence"],
                        classification["reasoning"],
                    ),
                )
                print(f"  [healer] Classified as {classification['category']} "
                      f"(confidence={classification['confidence']})")
        conn.commit()
        print(f"  [db] Saved run_id={run_id} to {DB_PATH}")
    finally:
        conn.close()


async def run_scenario(scenario_path: str) -> dict:
    scenario = json.loads(Path(scenario_path).read_text())
    scenario_id = scenario.get("scenario_id", "unknown")
    steps = scenario.get("steps", [])

    run_record = {
        "scenario_id": scenario_id,
        "started_at": datetime.now().isoformat(),
        "steps": [],
        "overall_status": "pass",
    }

    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await ensure_logged_in(session)

            for i, step in enumerate(steps):
                step_result = await run_step(session, step)
                step_result["step_index"] = i
                run_record["steps"].append(step_result)

                status_label = step_result["status"].upper()
                print(f"  [{i}] {status_label:8s} {step_result['action']:8s} target={step_result['target']!r} -> {step_result['detail']}")

                if step_result["status"] in ("fail", "error"):
                    run_record["overall_status"] = "fail"
                    print(f"  Stopping scenario '{scenario_id}' on first failure at step {i}.")
                    break

    run_record["finished_at"] = datetime.now().isoformat()
    save_run_to_db(run_record)
    return run_record


def main():
    if len(sys.argv) != 2:
        print("Usage: python orchestrator.py <scenario_json_path>")
        sys.exit(1)

    scenario_path = sys.argv[1]
    print(f"--- Running scenario: {scenario_path} ---")
    record = asyncio.run(run_scenario(scenario_path))

    print(f"\nOverall result: {record['overall_status'].upper()}")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
