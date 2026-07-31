"""
healer.py -- self-healing logic for the test automation agent.

Month 2, Step 1: rule-based failure classification (no LLM yet).
Given a failed step_result dict (as produced by orchestrator.run_step),
classify why it failed into a category, with a confidence score and
human-readable reasoning -- so downstream logic (and eventually an LLM
repair prompt) knows whether this is a real selector-drift candidate,
or something that should NOT be auto-healed.
"""


def classify_failure(step_result: dict) -> dict:
    """
    Classify a failed step into a category healer.py can act on.
    Returns {category, confidence, reasoning}.
    """
    raw = (step_result.get("raw_tool_output") or "").lower()
    detail = (step_result.get("detail") or "").lower()
    text = raw + " " + detail

    if "waiting for locator" in text and "to be visible" in text:
        return {
            "category": "SELECTOR_NOT_FOUND",
            "confidence": 0.9,
            "reasoning": "Playwright timed out waiting for the locator to become visible -- "
                         "the element never appeared. Strong candidate for selector drift."
        }
    if "waiting for locator" in text:
        return {
            "category": "SELECTOR_NOT_FOUND",
            "confidence": 0.75,
            "reasoning": "Playwright timed out waiting for the locator with no further detail. "
                         "Likely selector drift, but less certain than the visibility-specific case."
        }
    if "disabled" in text or "not enabled" in text:
        return {
            "category": "NOT_INTERACTABLE",
            "confidence": 0.85,
            "reasoning": "Element exists but is disabled -- likely a real app-state precondition "
                         "issue, not a selector problem. Should NOT be auto-healed."
        }
    if "intercepted" in text or "not visible" in text:
        return {
            "category": "NOT_INTERACTABLE",
            "confidence": 0.6,
            "reasoning": "Element may exist but is obstructed or hidden. Needs human judgment."
        }
    if step_result.get("action") == "assert" and "found_in_visible_text=false" in text:
        return {
            "category": "ASSERTION_MISMATCH",
            "confidence": 0.5,
            "reasoning": "Expected marker text did not appear. Could be selector drift, a real "
                         "app bug, or a bad test precondition (see Month 1's disabled-button case)."
        }
    return {
        "category": "UNKNOWN",
        "confidence": 0.3,
        "reasoning": "Failure text did not match any known pattern. Needs human review."
    }
