# Self-Healing AI Test Automation Agent — Salesforce B2B Commerce

An AI-assisted test automation pipeline for a simulated Salesforce B2B Commerce storefront, built around an LLM, an MCP Playwright server, and a self-healing agent that detects and proposes fixes for UI selector drift — with every proposal gated behind human review before it can ever be applied.

**Status:** PFA internship project — core pipeline complete, order-approval workflow now implemented natively in Salesforce. See [Current Status](#current-status) below.

---

## What this project does

Salesforce UI tests break constantly — not because of real bugs, but because Lightning components get restyled, renamed, or restructured. This project explores whether an LLM-based agent can:

1. **Generate** Playwright test scenarios directly from natural-language user stories.
2. **Execute** those scenarios against a real (simulated) Salesforce org.
3. **Self-heal** — when a test fails because a selector changed, diagnose the failure, propose a fix, attach a confidence score, and surface it for human approval before anything is ever applied automatically.

Since the target Salesforce Developer Edition org doesn't include the B2B Commerce managed package, the catalog/cart/checkout journeys are simulated using custom Lightning Web Components on standard Salesforce objects (`Product2`, `Pricebook2`, `PricebookEntry`, `Account`, `Order`) — preserving every technically relevant aspect (Shadow DOM, LWC rendering, selector drift, account-based pricing) without depending on an unavailable package.

---

## Architecture — pipeline order User story (natural language)
│
▼
┌───────────────────────────────────────────┐
│ generator.py [AI — LLM] │ Ollama (llama3.1:8b)
│ user story → structured scenario JSON │ Grounded in real data-testid values;
└───────────────────────────────────────────┘ explicit rule against inventing testids
│ for features that don't exist
▼
scenarios/*.json (validated test scenarios)
│
▼
┌───────────────────────────────────────────┐
│ orchestrator.py [automation only] │ MCP Playwright server
│ reads a scenario, executes it against the │ Auth via frontdoor.jsp session handoff
│ live org (navigate/click/fill/assert) │ Shadow-DOM-aware assertions (see below)
└───────────────────────────────────────────┘ Logs every run to SQLite
│ │
▼ ▼
PASS FAIL (selector drift suspected)
→ log result │
│ ▼
│ ┌───────────────────────────────────┐
│ │ healer.py [AI — LLM] │
│ │ classify failure → gather evidence │
│ │ → LLM-proposed fix + confidence → │
│ │ deterministic grounding check → │
│ │ human review (review_fixes.py) │
│ └───────────────────────────────────┘
│ │
▼ ▼
SQLite (runs / steps / failures / proposed_fixes)
│
▼
dashboard.py (Streamlit — run history, failure
breakdown, proposed fixes queue) 
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

A third instance of the same underlying pattern — trusting a confident-looking signal instead of verifying it — showed up outside the LLM entirely: `orchestrator.py` originally reported `PASS` on checkout scenarios purely because the "Submit Order" button was clickable, without ever confirming a real `Order` record was created. This was only caught by manually cross-checking with a direct SOQL query. See [Order approval workflow](#order-approval-workflow) below for the root cause and fix.

---

## Where the AI actually is (and isn't)

| Component | AI? | What it actually does |
|---|---|---|
| `generator.py` | **Yes** | Turns a user story into structured test steps, grounded in real deployed `data-testid` values, with an explicit rule against inventing testids for non-existent features. |
| LWC / Apex storefront | No | Standard Salesforce development (catalog, cart, checkout, account-based pricing, order approval). |
| `orchestrator.py` | No | Pure browser automation — reads JSON, calls MCP Playwright tools, logs results to SQLite. No LLM involved. |
| Auth (`frontdoor.jsp` handoff), Shadow-DOM-aware assertions, `scope_text` selector scoping | No | Salesforce/web engineering (MFA bypass via session-token handoff, marker-text-based waiting/assertion strategy, disambiguating repeated `data-testid`s across product cards). |
| `healer.py` | **Yes** | Classifies failures (rule-based), builds evidence from the live page, asks the LLM to propose a fix with reasoning, validates the proposal deterministically (rejecting circular or ungrounded guesses), and hands it to a human for final approval. |
| `review_fixes.py` | No | CLI tool for a human to approve/reject proposed fixes. The only place a fix can ever be marked `approved`. |
| `dashboard.py` | No | Read-only Streamlit view over run/failure/fix history. Does not take any action itself. |

---

## Tech stack

- **Language:** Python (orchestration), JavaScript (LWC), Apex (Salesforce backend)
- **LLM:** Ollama (local, `llama3.1:8b`, temperature=0 for repair proposals)
- **Browser automation:** MCP Playwright server (`@executeautomation/playwright-mcp-server`)
- **Target platform:** Salesforce Developer Edition (simulated B2B Commerce via custom LWCs)
- **Storage:** SQLite (`test_runs.db` — runs / steps / failures / proposed_fixes tables)
- **Reporting:** Streamlit dashboard (`dashboard.py`)

---

## Order approval workflow

Checkouts over **$10,000** require manager approval. This is implemented entirely natively in Salesforce — no external service, no Streamlit involvement:

1. **Buyer checks out** (`checkoutForm` LWC) — `CheckoutController.submitOrder()` creates the `Order` and sets `Approval_Required__c = true` if the total exceeds the threshold. This is a real `Order` record, not a simulated one — see the root-cause note below for why that distinction mattered.
2. If approval is required, the buyer sees a read-only generated email draft and a **Send Approval Request** button. Clicking it calls `CheckoutController.sendApprovalEmail()`, which sends a **real email** via `Messaging.sendEmail` to the Account owner and sets `Approval_Status__c = 'Pending'`.
3. The buyer's view then shows only an "awaiting manager decision" message — **no approve/reject controls are exposed to the buyer**, by design, since the buyer submitting the order should not also be able to approve it.
4. **The manager** reviews and decides on a **separate page** — `Manager Approvals` (`managerApproval` LWC, its own FlexiPage/tab, deployed independently of `Catalog_Test`). This page lists all `Approval_Status__c = 'Pending'` orders with Approve/Reject buttons (`CheckoutController.resolveApproval()`), and a Decision History section below listing every previously approved/rejected order (`CheckoutController.getApprovalHistory()`). History currently shows order creation date, not a separate decision timestamp — see Known issues.

**Root cause of the checkout test-coverage gap (now fixed):** `Order.AccountId` is a required field, populated from a `testAccountId` value that flows through `storefront`'s Lightning App Builder **design attribute** — a per-org UI configuration value that is *not* captured in git-tracked metadata by default. This was blank after the org migration, so every automated checkout silently failed to create a real `Order` while still reporting `PASS` (the click itself succeeded). The design attribute value is now also persisted directly inside `Catalog_Test.flexipage-meta.xml` (`<componentInstanceProperties>`) so it survives future deploys and org migrations without manual re-entry in App Builder — previously this had to be set by hand every time.

**Manual step still required after any fresh deploy of a *new* app page:** like `Catalog_Test` before it, `Manager_Approvals` needed a one-time manual activation (Setup → Lightning App Builder → Activation → assign a Tab Label → add to the Sales app's navigation) after its first deploy, since Salesforce does not auto-expose new AppPages in App Launcher. This is a Salesforce platform limitation, not something scriptable via `sf project deploy start`.

---

## Recent additions

Beyond the initial pipeline, the following were added across later work sessions on this project:

**Composite-action generator fix.** Compound/colloquial buyer stories (e.g. "buy X, 3 times at once") were originally either incorrectly flagged as `future_`/`NOT_IMPLEMENTED`, or correctly avoided hallucinating a testid but then silently dropped part of the story (a stated quantity, or the checkout step), or got step ordering wrong (setting quantity before the item was actually added to the cart). Fixed by adding an explicit `COMPOSITE ACTIONS` rule and a worked calibration example to `generator.py`'s `SYSTEM_PROMPT`, teaching it to decompose a compound story into every real implemented step, in the correct order. Covered by `test_composite_actions.py` and verified end-to-end against the live org across multiple phrasings ("buy"/"order"/"purchase").

**Catalog redesign and product categorization.** The storefront originally had no visual design (bare unstyled HTML) and a flat product list. Added a full CSS design pass across the catalog, cart, and checkout components, consistent with Salesforce's own Lightning Design System tokens. Added a `Product2.Category__c` custom field and grew the catalog from ~19 to 54 products across 7 categories. The catalog UI was then reworked into a two-level, category-drill-down experience: the top-level view shows category tiles only; clicking one filters to that category's products, with a "back to categories" control to return. This required corresponding updates to `generator.py`'s implemented-elements list and composite-action flow (a `category-tile` click is now a mandatory step before any `product-card` click) and to `orchestrator.py`'s `TESTID_MARKERS` (the initial catalog view's marker text changed, since "Add to Cart" no longer appears until a category is selected). Category tiles originally used emoji icons per category; these were later removed in favor of a plain accent-color left-border on each tile, for a more professional/less playful look.

**Live Demo page.** Added `pages/1_Live_Demo.py`, a Streamlit multipage view that lets a user type a user story, generate a scenario, and run it against the live org entirely through the browser — no terminal needed. On failure, it shows the same failure classification and self-healing proposal the CLI/dashboard show, resolved from the same SQLite tables. Includes an option to load an existing scenario file directly (useful for demoing a known selector-drift failure on demand).

**Environment/configuration hardening.** The live org URL was previously hardcoded in `orchestrator.py` and `scripts/login_test.py`; both now read it from an `SF_CATALOG_TEST_URL` environment variable instead, with no default pointing at a real org baked into the source.

**Org migration.** The project was migrated from an original Salesforce org (frozen by Salesforce's anomaly detection, likely a false positive from repeated automated `frontdoor.jsp` logins) to a fresh Developer Edition org. All code was already in git, so this was a recoverable, if time-consuming, detour — not data loss. One real gap was found and fixed in the process: `Account.Assigned_Price_Book__c`'s field metadata had never actually been committed to git (it was created directly in the old org's Setup UI before the track-custom-fields-as-source pattern was established), which caused the first deploy attempt on the new org to fail. This is now fixed and committed, so it won't recur on a future migration.

**Order approval workflow.** See the [dedicated section above](#order-approval-workflow) — implemented as real Apex-driven email plus a separate Manager Approvals page, after an earlier UI-only Streamlit simulation of this flow was abandoned in favor of building it natively in Salesforce.

**In progress:**
- An automated alert email sent when a test fails and a self-healing proposal is generated, so it doesn't require actively checking the dashboard. A fix for a real bug in this code path (`send_failure_alert()` referencing an out-of-scope `scenario_id`) has been written but never tested end-to-end.

---

## Current Status

| Area | Status |
|---|---|
| Salesforce environment & toolchain | ✅ Done |
| Storefront simulation (catalog, cart, checkout) | ✅ Done — verified end-to-end, including real `Order` creation on automated checkout |
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
| Composite-action generator fix | ✅ Done — regression-tested, verified against the live org |
| Product categorization + category drill-down catalog UX | ✅ Done — verified against the live org |
| Live Demo page (`pages/1_Live_Demo.py`) | ✅ Done — generate/run/self-heal entirely from the browser |
| Order approval workflow (real email + Manager Approvals page) | ✅ Done — verified end-to-end against the live org |
| Test-failure alert email | 🔄 In progress — fix written, not yet tested |

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

**Required environment variables** (set these before running `orchestrator.py`, or scenarios and alert emails will fail):
```bash
export SF_CATALOG_TEST_URL="https://YOUR-ORG-DOMAIN.develop.lightning.force.com/lightning/n/Catalog_Test"
export SMTP_SENDER_EMAIL="your-sender@gmail.com"
export SMTP_SENDER_PASSWORD="your-app-password"
export FAILURE_ALERT_RECIPIENT="recipient@example.com"
```
Note: the SMTP variables above are only used by `orchestrator.py`'s test-failure alert (still in progress). The order-approval email is sent natively via Apex `Messaging.sendEmail` and needs no external SMTP configuration — it just requires the target org's Email Deliverability setting (Setup → Email → Deliverability) to allow outbound mail.

**After any fresh deploy that introduces a new standalone App Page** (as happened for both `Catalog_Test` and `Manager_Approvals`): the page needs a one-time manual activation in Setup → Lightning App Builder → Activation, assigning it a tab and adding it to the relevant app's navigation. This is a Salesforce platform limitation and cannot be scripted via the CLI.

> **Note:** Python virtual environments are not relocatable — if you move this project folder, delete and recreate `venv/` rather than trying to reuse it (`rm -rf venv && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`).

---

## Known issues / open follow-ups

- A few `TESTID_MARKERS` entries in `orchestrator.py` (`cart-total`, `checkout-error`) have no unique literal text to key off of, since they render only dynamic numbers/JSON. These fall back to a generic mount-proxy marker, which confirms the storefront rendered but can't verify that specific element's exact state.
- One early `failures` row (`failure_id=1`) predates `classify_failure()` being wired into the pipeline and has a null category — a historical artifact, not a bug in the current pipeline.
- The heuristic used to extract `candidate_labels` from a visible-text snapshot in `healer.py` is a plain-text scan, not a real accessibility-tree walk; it works well in practice but is not guaranteed to find every relevant label on a more complex page than this project's catalog.
- Scenario files generated before the category drill-down catalog UX shipped click `product-card` directly without a preceding `category-tile` click, and will fail against the current catalog. These should be regenerated rather than assumed still valid.
- The Manager Approvals Decision History table shows order **creation date**, not the actual decision (approve/reject) timestamp, since that isn't tracked as a separate field. Adding an `Approval_Decided_Date__c` field, stamped at decision time, would make this accurate.
- `.sf/` (Salesforce CLI org auth/session data) is now excluded via `.gitignore` going forward, but was present in the very first commit to this repository. Any credentials/tokens from that point should be considered potentially exposed if this repository's visibility has ever been public; worth confirming current repo visibility and rotating org credentials if there's any doubt.
- `send_failure_alert()`'s `scenario_id` scoping bug fix is written (`patch_fix_scenario_id.py` equivalent, applied to `orchestrator.py`) but has never actually been run end-to-end.

---

## Author

**Youssef Mouhi** — Application Developer Intern (PFA)
Supervisor: Seddik Bourma
