# Self-Healing AI Test Automation Agent — Salesforce B2B Commerce

An AI-assisted test automation pipeline for a simulated Salesforce B2B Commerce storefront, built around an LLM, an MCP Playwright server, and (in progress) a self-healing agent that detects and proposes fixes for UI selector drift.

**Status:** PFA internship project, [redacted] — Month 1 complete, Month 2 (self-healing) starting. See [Current Status](#current-status) below for what's done vs. in progress.

---

## What this project does

Salesforce UI tests break constantly — not because of real bugs, but because Lightning components get restyled, renamed, or restructured. This project explores whether an LLM-based agent can:

1. **Generate** Playwright test scenarios directly from natural-language user stories.
2. **Execute** those scenarios against a real (simulated) Salesforce org.
3. **Self-heal** — when a test fails because a selector changed, diagnose the failure, propose a fix, attach a confidence score, and apply it automatically only after human validation.

Since the target Salesforce Developer Edition org doesn't include the B2B Commerce managed package, the catalog/cart/checkout journeys are simulated using custom Lightning Web Components on standard Salesforce objects (`Product2`, `Pricebook2`, `PricebookEntry`, `Account`, `Order`) — preserving every technically relevant aspect (Shadow DOM, LWC rendering, selector drift, account-based pricing) without depending on an unavailable package.

---

## Architecture — pipeline order

```
User story (natural language)
        │
        ▼
┌───────────────────────────────────────────┐
│ generator.py               [AI — LLM]      │   Ollama (llama3.1:8b)
│ user story → structured scenario JSON      │   Grounded in real data-testid values
└───────────────────────────────────────────┘
        │
        ▼
   scenarios/*.json   (validated test scenarios)
        │
        ▼
┌───────────────────────────────────────────┐
│ orchestrator.py         [automation only]  │   MCP Playwright server
│ reads a scenario, executes it against the  │   Auth via frontdoor.jsp session handoff
│ live org (navigate/click/fill/assert)      │   Shadow-DOM-aware assertions (see below)
└───────────────────────────────────────────┘
        │                         │
        ▼                         ▼
     PASS                       FAIL  (selector drift suspected)
   → log result                   │
        │                         ▼
        │              ┌───────────────────────────────────┐
        │              │ healer.py      [AI — NOT YET BUILT]│
        │              │ failed selector + step intent +    │
        │              │ visible-text snapshot (see note)   │
        │              │ → LLM-proposed fix + confidence     │
        │              │ → human validation before auto-apply│
        │              └───────────────────────────────────┘
        │                         │
        ▼                         ▼
              SQLite (run history)  ✅ implemented
                       │
                       ▼
              Streamlit dashboard  (not yet built)
```

**Read in order:** a user story goes into `generator.py` (the only component that currently calls an LLM), producing a validated scenario file. `orchestrator.py` — pure browser automation, no AI — executes that scenario against the live simulated storefront, and now logs every run to SQLite. On failure, `healer.py` (Week 4, not yet built) will be the actual self-healing agent: it inspects the failure evidence available at that point (see the Shadow DOM note below — a literal DOM diff isn't possible here), asks the LLM to propose a fix with a confidence score, and only applies it automatically after a human validates it.

---

## Important technical note: LWC uses closed Shadow DOM

A significant finding from Month 1: Salesforce LWC renders with **closed native Shadow DOM** by default. This has a real consequence for both `orchestrator.py` and the planned `healer.py`:

- `document.querySelectorAll(...)` and Playwright's `get_visible_html` **cannot see inside any LWC component** — `element.shadowRoot` returns `null` for closed roots even though the shadow root genuinely exists and is rendering.
- Playwright's **click/fill actions** operate at the browser-engine level (via CDP) and are unaffected — they can target elements inside closed shadow roots correctly.
- `playwright_get_visible_text` reflects the accessibility tree, which also correctly crosses closed shadow boundaries.

**Practical impact:** `orchestrator.py`'s existence/assertion checks were rewritten to poll `get_visible_text` for known literal marker text per `data-testid` (see `TESTID_MARKERS` in `orchestrator.py`), instead of relying on DOM queries, which were structurally guaranteed to fail. This also means `healer.py` cannot build a traditional DOM diff — its repair-prompt input will need to be based on before/after visible-text snapshots and the literal failed selector, not DOM serialization.

---

## Where the AI actually is (and isn't) — right now

It's easy to assume a project named "AI agent" is AI throughout. As of Month 1, that's not accurate, and it's worth being precise:

| Component | AI? | What it actually does |
|---|---|---|
| `generator.py` | **Yes** | Only component using an LLM so far. Turns a user story into structured test steps, grounded in real deployed `data-testid` values to prevent hallucinated selectors. |
| LWC / Apex storefront | No | Standard Salesforce development (catalog, cart, checkout, account-based pricing). |
| `orchestrator.py` | No | Pure browser automation — reads JSON, calls MCP Playwright tools, logs results to SQLite. No LLM involved. |
| Auth (`frontdoor.jsp` handoff), Shadow-DOM-aware assertions, `scope_text` selector scoping | No | Salesforce/web engineering (MFA bypass via session-token handoff, marker-text-based waiting/assertion strategy, disambiguating repeated `data-testid`s across product cards). |
| `healer.py` | **Yes — not built yet** | The actual self-healing reasoning loop: detect → gather failure evidence (visible-text snapshot + failed selector, not a DOM diff — see note above) → propose fix via LLM → confidence score → human validation. This is the differentiating AI contribution of the project and is the priority for Month 2. |

---

## Tech stack

- **Language:** Python (orchestration), JavaScript (LWC)
- **LLM:** Ollama (local, `llama3.1:8b`) — Claude API as the documented fallback path
- **Browser automation:** MCP Playwright server (`@executeautomation/playwright-mcp-server`)
- **Target platform:** Salesforce Developer Edition (simulated B2B Commerce via custom LWCs)
- **Storage:** SQLite (`test_runs.db` — runs / steps / failures tables)
- **Reporting:** Streamlit dashboard (not yet started)

---

## Current Status

| Area | Status |
|---|---|
| Salesforce environment & toolchain | ✅ Done |
| Storefront simulation (catalog, cart, checkout) | ✅ Done — verified end-to-end |
| Account-based pricing | ✅ Done — verified at Apex level |
| Scenario generator (`generator.py`) | ✅ Done — 10 scenarios grounded & validated |
| MCP Playwright integration | ✅ Done |
| Authentication (`frontdoor.jsp` session handoff, MFA bypass) | ✅ Done |
| Execution pipeline (`orchestrator.py`) | ✅ Done — Shadow-DOM-aware assertions, `scope_text` selector scoping |
| Full scenario validation run | ✅ Done — 9/9 real scenarios pass (1 scenario correctly marked `future_` — tests a feature not yet built) |
| SQLite run-history logging | ✅ Done — `runs` / `steps` / `failures` tables, wired into every scenario run |
| Self-healing module (`healer.py`) | ⬜ Not started — Month 2 priority, starting now |
| Streamlit dashboard | ⬜ Not started |

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

# Run a scenario
python3 orchestrator.py scenarios/view_products.json

# Run the full suite
for f in scenarios/*.json; do python3 orchestrator.py "$f"; done

# Inspect run history
python3 -c "
import sqlite3
conn = sqlite3.connect('test_runs.db')
for row in conn.execute('SELECT * FROM runs'):
    print(row)
"
```

> **Note:** Python virtual environments are not relocatable — if you move this project folder, delete and recreate `venv/` rather than trying to reuse it (`rm -rf venv && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`).

---

## Known issues / open follow-ups

- `future_search_product.json` tests a search feature that doesn't exist in the storefront yet — correctly failing/excluded, but `enforce_future_prefix()` in `generator.py` should be fixed to auto-detect this case rather than relying on a manual rename.
- A few `TESTID_MARKERS` entries (`cart-total`, `debug-raw-cart`, `checkout-error`) have no unique literal text to key off of, since they render only dynamic numbers/JSON. These currently fall back to a generic mount-proxy marker, which confirms the storefront rendered but can't verify that specific element's exact state.

---

## Author

**Youssef Mouhi** — Application Developer Intern (PFA), [redacted]
Supervisor: Seddik Bourma
