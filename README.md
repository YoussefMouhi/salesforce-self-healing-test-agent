# Self-Healing AI Test Automation Agent — Salesforce B2B Commerce

An AI-assisted test automation pipeline for a simulated Salesforce B2B Commerce storefront, built around an LLM, an MCP Playwright server, and (in progress) a self-healing agent that detects and proposes fixes for UI selector drift.

**Status:** PFA internship project, [redacted] — Month 1 of 2 complete. See [Current Status](#current-status) below for what's done vs. in progress.

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
│ live org (navigate/click/fill/assert)      │   (bypasses mandatory Salesforce MFA)
└───────────────────────────────────────────┘
        │                         │
        ▼                         ▼
     PASS                       FAIL  (selector drift suspected)
   → log result                   │
        │                         ▼
        │              ┌───────────────────────────────────┐
        │              │ healer.py      [AI — NOT YET BUILT]│
        │              │ DOM diff + failed step intent      │
        │              │ → LLM-proposed fix + confidence     │
        │              │ → human validation before auto-apply│
        │              └───────────────────────────────────┘
        │                         │
        ▼                         ▼
              SQLite (run history)
                       │
                       ▼
              Streamlit dashboard
```

**Read in order:** a user story goes into `generator.py` (the only component that currently calls an LLM), producing a validated scenario file. `orchestrator.py` — pure browser automation, no AI — executes that scenario against the live simulated storefront. On failure, `healer.py` (Week 4, not yet built) will be the actual self-healing agent: it inspects the DOM at the moment of failure, asks the LLM to propose a fix with a confidence score, and only applies it automatically after a human validates it. Every run, healed or not, is logged to SQLite and surfaced on a Streamlit dashboard.

---

## Where the AI actually is (and isn't) — right now

It's easy to assume a project named "AI agent" is AI throughout. As of Month 1, that's not accurate, and it's worth being precise:

| Component | AI? | What it actually does |
|---|---|---|
| `generator.py` | **Yes** | Only component using an LLM so far. Turns a user story into structured test steps, grounded in real deployed `data-testid` values to prevent hallucinated selectors. |
| LWC / Apex storefront | No | Standard Salesforce development (catalog, cart, checkout, account-based pricing). |
| `orchestrator.py` | No | Pure browser automation — reads JSON, calls MCP Playwright tools. No LLM involved. |
| Auth (`frontdoor.jsp` handoff) & wait-function fixes | No | Salesforce/web engineering (MFA bypass via session-token handoff, Shadow-DOM-aware polling). |
| `healer.py` | **Yes — not built yet** | The actual self-healing reasoning loop: detect → inspect DOM → propose fix via LLM → confidence score → human validation. This is the differentiating AI contribution of the project and is the priority for Month 2. |

---

## Tech stack

- **Language:** Python (orchestration), JavaScript (LWC)
- **LLM:** Ollama (local, `llama3.1:8b`) — Claude API as the documented fallback path
- **Browser automation:** MCP Playwright server (`@executeautomation/playwright-mcp-server`)
- **Target platform:** Salesforce Developer Edition (simulated B2B Commerce via custom LWCs)
- **Storage:** SQLite (run history — in progress)
- **Reporting:** Streamlit dashboard (not yet started)

---

## Current Status

| Area | Status |
|---|---|
| Salesforce environment & toolchain | ✅ Done |
| Storefront simulation (catalog, cart, checkout) | ✅ Done — verified end-to-end |
| Account-based pricing | ✅ Done — verified at Apex level |
| Scenario generator (`generator.py`) | ✅ Done — 10/10 scenarios grounded & validated |
| MCP Playwright integration | ✅ Done |
| Authentication (`frontdoor.jsp` session handoff, MFA bypass) | ✅ Done |
| Execution pipeline (`orchestrator.py`) | 🟡 In progress — Shadow-DOM wait-function fix being wired in |
| Full 10-scenario validation run | 🟡 In progress |
| SQLite run-history logging | ⬜ Not started |
| Self-healing module (`healer.py`) | ⬜ Not started — Month 2 priority |
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
python orchestrator.py scenarios/view_products.json
```

---

## Known issues (actively being worked on)

- `wait_for_element()` in `orchestrator.py` currently uses a plain `document.querySelectorAll()` check, which cannot see through Shadow DOM. A shadow-piercing version has been diagnosed and is being wired into the `navigate` step path.
- A handful of scenarios assume application state (e.g. items already in the cart) that isn't guaranteed given each script run starts from a fresh, unauthenticated browser session — these will be reviewed once the wait-function fix lands.

---

## Author

**Youssef Mouhi** — Application Developer Intern (PFA), [redacted]
Supervisor: Seddik Bourma
