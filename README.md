# Self-Healing AI Test Automation Agent — Salesforce B2B Commerce

An AI-assisted test automation pipeline for a simulated Salesforce B2B Commerce storefront, built around an LLM, an MCP Playwright server, and a self-healing agent that detects and proposes fixes for UI selector drift — with every proposal gated behind human review before it can ever be applied.

**Status:** PFA internship project, [redacted] — complete. See [Current Status](#current-status) below.

---

## What this project does

Salesforce UI tests break constantly — not because of real bugs, but because Lightning components get restyled, renamed, or restructured. This project explores whether an LLM-based agent can:

1. **Generate** Playwright test scenarios directly from natural-language user stories.
2. **Execute** those scenarios against a real (simulated) Salesforce org.
3. **Self-heal** — when a test fails because a selector changed, diagnose the failure, propose a fix, attach a confidence score, and surface it for human approval before anything is ever applied automatically.

Since the target Salesforce Developer Edition org doesn't include the B2B Commerce managed package, the catalog/cart/checkout journeys are simulated using custom Lightning Web Components on standard Salesforce objects (`Product2`, `Pricebook2`, `PricebookEntry`, `Account`, `Order`) — preserving every technically relevant aspect (Shadow DOM, LWC rendering, selector drift, account-based pricing) without depending on an unavailable package.

---

## Architecture — pipeline order

```
User story (natural language)
        │
        ▼
┌───────────────────────────────────────────┐
│ generator.py               [AI — LLM]      │   Ollama (llama3.1:8b)
│ user story → structured scenario JSON      │   Grounded in real data-testid values;
└───────────────────────────────────────────┘   explicit rule against inventing testids
        │                                        for features that don't exist
        ▼
   scenarios/*.json   (validated test scenarios)
        │
        ▼
┌───────────────────────────────────────────┐
│ orchestrator.py         [automation only]  │   MCP Playwright server
│ reads a scenario, executes it against the  │   Auth via frontdoor.jsp session handoff
│ live org (navigate/click/fill/assert)      │   Shadow-DOM-aware assertions (see below)
└───────────────────────────────────────────┘   Logs every run to SQLite
        │                         │
        ▼                         ▼
     PASS                       FAIL  (selector drift suspected)
   → log result                   │
        │                         ▼
        │              ┌───────────────────────────────────┐
        │              │ healer.py            [AI — LLM]    │
        │              │ classify failure → gather evidence │
        │              │ → LLM-proposed fix + confidence →  │
        │              │ deterministic grounding check →    │
        │              │ human review (review_fixes.py)     │
        │              └───────────────────────────────────┘
        │                         │
        ▼                         ▼
              SQLite (runs / steps / failures / proposed_fixes)
                       │
                       ▼
              dashboard.py  (Streamlit — run history, failure
                              breakdown, proposed fixes queue)
```

**Read in order:** a user story goes into `generator.py`, producing a validated scenario file. `orchestrator.py` — pure browser automation, no AI — executes that scenario against the live simulated storefront and logs every run to SQLite. On failure, `healer.py` classifies the failure, gathers the best available evidence (a visible-text snapshot — see the Shadow DOM note below for why a real DOM diff isn't possible), asks the LLM to propose a fix, runs the proposal through a deterministic validation gate, and — only after a human explicitly approves it via `review_fixes.py` — the fix is ready to apply. Nothing in this project auto-applies a proposed fix. Every run and every proposal is visible on the `dashboard.py` Streamlit dashboard.

---

## Important technical note: LWC uses closed Shadow DOM

A significant finding from this project: Salesforce LWC renders with **closed native Shadow DOM** by default. This has a real consequence for both `orchestrator.py` and `healer.py`:

- `document.querySelectorAll(...)` and Playwright's `get_visible_html` **cannot see inside any LWC component** — `element.shadowRoot` returns `null` for closed roots even though the shadow root genuinely exists and is rendering.
- Playwright's **click/fill actions** operate at the browser-engine level (via CDP) and are unaffected — they can target elements inside closed shadow roots correctly.
- `playwright_get_visible_text` reflects the accessibility tree, which also correctly crosses closed shadow boundaries.

**Practical impact:** `orchestrator.py`'s existence/assertion checks poll `get_visible_text` for known literal marker text per `data-testid` (see `TESTID_MARKERS`), instead of relying on DOM queries, which were structurally guaranteed to fail. This also means `healer.py` cannot build a traditional DOM diff — its repair-prompt input is built from before/after visible-text snapshots and the literal failed selector, not DOM serialization.

A second, independently discovered issue: the MCP Playwright server's `isError` field is **not reliable** for `playwright_click`/`playwright_fill` — a genuinely failed click (e.g. timing out waiting for a locator) was observed returning `isError: False`. `orchestrator.py` now also checks the tool's own text output for failure phrases (`"timeout"`, `"operation failed"`, etc.) rather than trusting `isError` alone.

---

## Important finding: the LLM hallucinates plausible answers instead of admitting uncertainty

This pattern showed up **independently in two different parts of the pipeline**, and was fixed the same way both times — which is itself a useful finding, not just a bug report:

1. **In `generator.py`:** asked to generate a test for a search feature that doesn't exist anywhere in the app, the LLM invented a plausible-sounding `data-testid` (`"search-input"`) instead of recognizing the feature wasn't implemented. Fixed by adding an explicit rule and a worked calibration example to `SYSTEM_PROMPT`, instructing the model to use a literal `"NOT_IMPLEMENTED"` sentinel rather than guessing — verified against a real regeneration, which now correctly outputs `"target": "NOT_IMPLEMENTED"` and a `future_`-prefixed scenario_id.
2. **In `healer.py`:** given a genuinely nonexistent search feature to repair, the LLM proposed `"search-input-field"` with `has_confident_match: true`, reasoning that "the target's name suggests a search input field" — a hallucination derived from the failed selector's own name, not from any real page evidence. Fixed with a deterministic grounding check in `validate_repair_proposal()`: any proposed testid must contain a word that literally appears in the real evidence (`candidate_labels`) captured at failure time, or it is rejected regardless of the model's stated confidence.

**Takeaway:** prompt-level instructions alone are not sufficient to prevent an LLM from producing confident-sounding but ungrounded output. Both fixes needed a deterministic, code-level check that does not trust the model's self-reported confidence — the model's own reasoning text sounded plausible in both cases, right up until it was checked against real evidence.

---

## Where the AI actually is (and isn't)

| Component | AI? | What it actually does |
|---|---|---|
| `generator.py` | **Yes** | Turns a user story into structured test steps, grounded in real deployed `data-testid` values, with an explicit rule against inventing testids for non-existent features. |
| LWC / Apex storefront | No | Standard Salesforce development (catalog, cart, checkout, account-based pricing). |
| `orchestrator.py` | No | Pure browser automation — reads JSON, calls MCP Playwright tools, logs results to SQLite. No LLM involved. |
| Auth (`frontdoor.jsp` handoff), Shadow-DOM-aware assertions, `scope_text` selector scoping | No | Salesforce/web engineering (MFA bypass via session-token handoff, marker-text-based waiting/assertion strategy, disambiguating repeated `data-testid`s across product cards). |
| `healer.py` | **Yes** | Classifies failures (rule-based), builds evidence from the live page, asks the LLM to propose a fix with reasoning, validates the proposal deterministically (rejecting circular or ungrounded guesses), and hands it to a human for final approval. |
| `review_fixes.py` | No | CLI tool for a human to approve/reject proposed fixes. The only place a fix can ever be marked `approved`. |
| `dashboard.py` | No | Read-only Streamlit view over run/failure/fix history. Does not take any action itself. |

---

## Tech stack

- **Language:** Python (orchestration), JavaScript (LWC)
- **LLM:** Ollama (local, `llama3.1:8b`, temperature=0 for repair proposals)
- **Browser automation:** MCP Playwright server (`@executeautomation/playwright-mcp-server`)
- **Target platform:** Salesforce Developer Edition (simulated B2B Commerce via custom LWCs)
- **Storage:** SQLite (`test_runs.db` — runs / steps / failures / proposed_fixes tables)
- **Reporting:** Streamlit dashboard (`dashboard.py`)

---

## Current Status

| Area | Status |
|---|---|
| Salesforce environment & toolchain | ✅ Done |
| Storefront simulation (catalog, cart, checkout) | ✅ Done — verified end-to-end |
| Account-based pricing | ✅ Done — verified at Apex level |
| Scenario generator (`generator.py`) | ✅ Done — including the not-implemented-feature hallucination fix |
| MCP Playwright integration | ✅ Done |
| Authentication (`frontdoor.jsp` session handoff, MFA bypass) | ✅ Done |
| Execution pipeline (`orchestrator.py`) | ✅ Done — Shadow-DOM-aware assertions, reliable failure detection, `scope_text` selector scoping |
| Full scenario validation run | ✅ Done — real scenarios pass; `future_search_product.json` correctly and reliably fails/skips |
| SQLite run-history logging | ✅ Done |
| Self-healing module (`healer.py`) | ✅ Done — classify → evidence → LLM proposal → deterministic validation → human review, all tested against real (not just synthetic) failures |
| Human review tool (`review_fixes.py`) | ✅ Done |
| Streamlit dashboard (`dashboard.py`) | ✅ Done |

---

## Setup

```bash
# Salesforce CLI + org
sf org login web -a devOrg
sf project deploy start

# Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Node / MCP Playwright server
npm install
npx playwright install chromium

# Ollama (local LLM)
ollama serve &
ollama pull llama3.1:8b

# Generate a new scenario from a user story
python3 generator.py

# Run a scenario
python3 orchestrator.py scenarios/view_products.json

# Run the full suite
for f in scenarios/*.json; do python3 orchestrator.py "$f"; done

# Review any pending self-healing proposals
python3 review_fixes.py

# Launch the dashboard
streamlit run dashboard.py
```

> **Note:** Python virtual environments are not relocatable — if you move this project folder, delete and recreate `venv/` rather than trying to reuse it (`rm -rf venv && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`).

---

## Known issues / open follow-ups

- A few `TESTID_MARKERS` entries in `orchestrator.py` (`cart-total`, `debug-raw-cart`, `checkout-error`) have no unique literal text to key off of, since they render only dynamic numbers/JSON. These fall back to a generic mount-proxy marker, which confirms the storefront rendered but can't verify that specific element's exact state.
- One early `failures` row (`failure_id=1`) predates `classify_failure()` being wired into the pipeline and has a null category — a historical artifact, not a bug in the current pipeline.
- The heuristic used to extract `candidate_labels` from a visible-text snapshot in `healer.py` is a plain-text scan, not a real accessibility-tree walk; it works well in practice but is not guaranteed to find every relevant label on a more complex page than this project's catalog.

---

## Author

**Youssef Mouhi** — Application Developer Intern (PFA), [redacted]
Supervisor: Seddik Bourma
