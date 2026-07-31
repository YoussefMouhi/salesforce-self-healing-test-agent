"""
healer.py -- self-healing logic for the test automation agent.

Month 2, Step 1: rule-based failure classification (no LLM yet).
Month 2, Step 2: evidence gathering for repair prompts.
"""

import re


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


# --- Evidence gathering for repair prompts -----------------------------

# LWC's closed Shadow DOM means we cannot get a real DOM diff (see README's
# Shadow DOM note). The best available evidence is a visible-text snapshot
# of the live page at failure time, plus a heuristic scan for words that
# *look* like they could be testid-ish labels (product names, button
# labels, etc.) near the original target name -- giving the LLM something
# concrete to reason about instead of just the bare failed selector.

# Generic Salesforce Lightning chrome that appears on every page regardless
# of which app-specific component is loaded. Filtered out because it is
# never a legitimate repair target for OUR storefront's selectors, and
# including it risks the LLM proposing a fix that points at unrelated
# platform UI (e.g. "Search Salesforce" for a failed app-specific search
# feature -- a real false-positive risk observed during testing).
_SALESFORCE_CHROME_NOISE = {
    "sfdclogo", "sorry to interrupt", "css error", "search salesforce",
    "open menu item submenu", "skip to navigation", "skip to main content",
    "menu", "developer edition", "show menu", "search...", "add favorite",
    "favorites list", "global actions", "salesforce help", "setup",
    "notifications", "view profile", "app launcher", "sales", "home",
    "just so you know",
}

# Marker text that indicates where OUR app's own content starts in the
# visible-text dump, so we skip past generic Lightning chrome instead of
# just taking the first N lines of the page.
_APP_CONTENT_START_MARKER = "catalog test"


def extract_candidate_labels(visible_text: str, max_candidates: int = 25) -> list[str]:
    """
    Pull short, label-like lines out of a visible-text snapshot: things
    that look like button text, field labels, or component headers rather
    than long sentences or pure numbers. This is a heuristic, not a real
    DOM inspection -- it's meant to give the LLM plausible candidates to
    reason about, not a guaranteed-correct list.

    Skips generic Salesforce Lightning chrome (nav bar, global search,
    setup menu, etc.) and starts scanning from our own app's content
    marker, since that chrome is never a legitimate repair target and
    risks misleading the LLM (see _SALESFORCE_CHROME_NOISE).
    """
    lines = visible_text.splitlines()

    # Find where our app's own content starts; if the marker isn't found,
    # fall back to scanning the whole thing (better than returning nothing).
    start_idx = 0
    for i, line in enumerate(lines):
        if _APP_CONTENT_START_MARKER in line.strip().lower():
            start_idx = i + 1
            break

    candidates = []
    for line in lines[start_idx:]:
        line = line.strip()
        if not line:
            continue
        if line.lower() in _SALESFORCE_CHROME_NOISE:
            continue
        if re.fullmatch(r"[\d.,$]+", line):
            continue
        if len(line) > 40:
            continue
        candidates.append(line)
        if len(candidates) >= max_candidates:
            break
    return candidates


def build_repair_evidence(step_result: dict, visible_text: str) -> dict:
    """
    Assemble everything the repair-prompt step will need: the original
    failed selector/testid, the step's intent (action + any value), the
    classification, and a heuristic list of candidate labels from the
    live page -- NOT a DOM diff, since closed Shadow DOM makes a real one
    unavailable (see README's Shadow DOM note for why).
    """
    classification = classify_failure(step_result)
    return {
        "failed_action": step_result.get("action"),
        "failed_target": step_result.get("target"),
        "failed_value": step_result.get("value"),
        "classification": classification,
        "candidate_labels": extract_candidate_labels(visible_text),
    }


# --- Repair prompt construction ----------------------------------------

def build_repair_prompt(evidence: dict) -> str:
    """
    Construct the prompt sent to the local LLM to propose a corrected
    selector, given the failure evidence. Explicit that:
      - only SELECTOR_NOT_FOUND failures should reach this point (the
        caller is responsible for that gate -- this function does not
        re-check classification itself)
      - the candidate list is text visible on the page, NOT a real DOM
        listing (LWC's closed Shadow DOM makes a real DOM diff impossible
        -- see README's Shadow DOM note)
      - the model should say "no confident match" rather than force a
        guess, since a wrong forced guess is worse than an honest failure
    """
    classification = evidence["classification"]
    candidates = evidence["candidate_labels"]
    candidates_block = "\n".join(f"- {c}" for c in candidates) if candidates else "(none captured)"

    return f"""You are helping repair a broken UI test selector for a Salesforce Lightning Web Component storefront.

IMPORTANT CONTEXT:
- This page uses closed native Shadow DOM, so we cannot give you a real DOM tree or HTML.
- The list below is plain VISIBLE TEXT captured from the page after the failure, not a DOM listing. It may include unrelated Lightning platform chrome as well as our app's real content.
- Only propose a fix if you are genuinely confident. If nothing in the text plausibly corresponds to the missing element, say so explicitly rather than guessing.

FAILED STEP:
- Action: {evidence['failed_action']}
- Original target (data-testid): {evidence['failed_target']}
- Value being entered (if any): {evidence['failed_value']}

FAILURE CLASSIFICATION (from rule-based analysis, not you):
- Category: {classification['category']}
- Reasoning: {classification['reasoning']}

VISIBLE TEXT ON THE PAGE AFTER THE FAILURE (candidate labels, may include noise):
{candidates_block}

CRITICAL RULE: proposed_testid_guess must NEVER be identical to the original failed target ("{evidence['failed_target']}"). If your answer would just repeat the original target, that is not a repair -- set has_confident_match to false instead.

HOW TO PROPOSE A TESTID GUESS: convert a visible label into kebab-case (lowercase, words joined by hyphens, no punctuation). For example, the visible text "Add to Cart" would become the testid guess "add-to-cart" or "add-to-cart-button". Only do this if a specific visible label plausibly matches the *purpose* implied by the original failed target's name -- do not guess based on the original target's name alone.

EXAMPLE 1 (no match -- calibration):
Failed target: "search-input". Visible text only shows product names and "Add to Cart" buttons, no search box or field mentioned anywhere.
{{"has_confident_match": false, "proposed_testid_guess": null, "reasoning": "No search-related element appears in the visible text; only product listings and add-to-cart buttons are present."}}

EXAMPLE 2 (match found -- calibration):
Failed target: "add-to-cart-btn-v2". Visible text repeatedly shows the literal button label "Add to Cart" next to each product.
{{"has_confident_match": true, "proposed_testid_guess": "add-to-cart-button", "reasoning": "The failed target's name suggests an add-to-cart button, and the visible label \'Add to Cart\' appears repeatedly next to products, strongly matching that purpose. Proposed a kebab-case testid derived from that visible label, NOT the original failed target name."}}

TASK:
Based only on the evidence above, answer in this exact JSON format and nothing else:
{{
  "has_confident_match": true or false,
  "proposed_testid_guess": "your best guess at a replacement data-testid value, or null if has_confident_match is false",
  "reasoning": "one or two sentences explaining your answer, referencing specific text above if relevant"
}}

Do not invent a testid value if nothing in the visible text plausibly represents the missing element -- in that case, set has_confident_match to false and proposed_testid_guess to null.
"""


# --- LLM call -----------------------------------------------------------

import json as _json
import urllib.request as _urllib_request


def call_ollama_repair(prompt: str, model: str = "llama3.1:8b", host: str = "http://localhost:11434") -> dict:
    """
    Send the repair prompt to the local Ollama model and parse its JSON
    response. Returns a dict with keys: has_confident_match,
    proposed_testid_guess, reasoning -- or an error dict if the call
    failed or the response wasn't valid JSON.
    """
    payload = _json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }).encode("utf-8")

    req = _urllib_request.Request(
        f"{host}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with _urllib_request.urlopen(req, timeout=60) as resp:
            body = _json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {
            "has_confident_match": False,
            "proposed_testid_guess": None,
            "reasoning": f"[ollama call failed: {e}]",
            "_error": True,
        }

    raw_response_text = body.get("response", "")
    try:
        parsed = _json.loads(raw_response_text)
        parsed.setdefault("has_confident_match", False)
        parsed.setdefault("proposed_testid_guess", None)
        parsed.setdefault("reasoning", "")
        return parsed
    except Exception as e:
        return {
            "has_confident_match": False,
            "proposed_testid_guess": None,
            "reasoning": f"[failed to parse model output as JSON: {e}] raw={raw_response_text!r}",
            "_error": True,
        }


# --- Post-hoc validation of LLM repair proposals ------------------------

def validate_repair_proposal(evidence: dict, llm_result: dict) -> dict:
    """
    Deterministic sanity checks on the LLM's proposal, run regardless of
    the model's own has_confident_match/confidence claims -- those have
    been observed to be unreliable (e.g. llama3.1:8b proposing the exact
    same testid that already failed, with non-sequitur reasoning).

    Returns llm_result with has_confident_match forced to False and a
    rejection reason appended if any check fails. This function is the
    real gate; the model\'s self-reported confidence is advisory only.
    """
    if not llm_result.get("has_confident_match"):
        return llm_result

    guess = llm_result.get("proposed_testid_guess")
    original = evidence.get("failed_target")

    if not guess:
        llm_result["has_confident_match"] = False
        llm_result["reasoning"] += " [REJECTED: has_confident_match=true but no guess provided]"
        return llm_result

    if guess.strip() == (original or "").strip():
        llm_result["has_confident_match"] = False
        llm_result["reasoning"] += (
            f" [REJECTED: proposed testid '{guess}' is identical to the "
            f"original failed target -- not a repair, likely model overconfidence]"
        )
        return llm_result

    return llm_result
