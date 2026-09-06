import json
from pathlib import Path

import requests
from jsonschema import validate, ValidationError

SCHEMA_PATH = Path(__file__).parent / "schemas" / "scenario_schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text())

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.1:8b"

SYSTEM_PROMPT = """You are a test scenario generator for a Salesforce B2B Commerce test suite simulated with Lightning Web Components.

Given a user story written in plain English, output ONLY valid JSON (no prose, no markdown fences, no explanation) matching this exact schema:

{
  "scenario_id": "short_snake_case_id",
  "steps": [
    {"action": "navigate|click|fill|assert|login", "target": "data-testid value or description", "value": "optional input value", "expected": "optional expected result for assert steps"}
  ]
}

Rules:
- Use "action" values from this set only: navigate, click, fill, assert, login.
- Keep steps atomic: one user action per step.
- Do not include any text outside the JSON object.
- Every assertion step's "expected" field must directly reflect the core need in the user story. If the story is about price, the final assertion MUST target price, not name or something else.

IMPLEMENTED elements (use these data-testid values, they are real and exist today):
- "category-tile" (clickable tile shown on the initial catalog view; use the "value" field to specify which category, e.g. "Fuel & Consumables")
- "category-name" (text label inside a category tile, not clickable itself)
- "back-to-categories" (button that returns from a filtered product view back to the category grid)
- "product-catalog" (container for the full product list)
- "product-card" (one row per product)
- "product-name" (product name text)
- "product-price" (product price text)
- "add-to-cart-button" (adds a product to the cart)
- "cart-summary" (container for the cart)
- "cart-item" (one row per cart line item)
- "cart-item-name", "cart-item-quantity", "cart-item-remove" (cart line item fields/controls)
- "cart-total" (running cart total)
- "checkout-form" (checkout container)
- "checkout-total" (total shown at checkout)
- "checkout-approval-warning" (shown when order total exceeds $10,000)
- "checkout-submit-button" (submits the order)

CRITICAL RULE -- features NOT in the list above (e.g. search, filtering, sorting,
wishlists, product reviews, discount codes, or ANY other feature not explicitly
named above) DO NOT EXIST in this app. If a user story requires interacting with
something not on the implemented-elements list, you MUST NOT invent a plausible-
sounding data-testid for it (e.g. do not guess "search-input" for a search
feature just because the name sounds reasonable). Instead, that step's "target"
MUST be the literal string "NOT_IMPLEMENTED", and the scenario_id MUST start
with "future_".

COMPOSITE ACTIONS -- before concluding a story is NOT_IMPLEMENTED, check whether
it can be satisfied by CHAINING two or more IMPLEMENTED elements together, even
if the story uses a single colloquial verb (e.g. "buy", "order", "purchase",
"get") that has no single matching testid of its own. These verbs almost always
map to the real multi-step flow, IN THIS EXACT ORDER: navigate to
product-catalog -> click the category-tile for the product's category -> click
the product-card -> click add-to-cart-button -> (if a quantity or repeat count
is mentioned) fill cart-item-quantity -> click checkout-submit-button. The
catalog shows CATEGORIES first, not individual products -- a product-card is
not reachable until its category-tile has been clicked, so this step can never
be skipped, even if the story doesn't mention a category explicitly. Known
categories today: "Fuel & Consumables", "Generators", "Installation", "Parts &
Accessories", "Service Plans", "Test Data", "Training & Support". Infer the
single best-matching category from the product name in the story (e.g. a
fuel/oil/coolant product -> "Fuel & Consumables") and set it as the "value" on
the category-tile step. Quantity can only be set on an item already in the
cart, so add-to-cart-button MUST come before cart-item-quantity, never after.
Do not drop or silently skip part of the story (e.g. a stated quantity, or the
checkout step) just because no single element matches that word -- decompose
the full story into every real step it implies, in the order a real user would
actually perform them. Only mark a story NOT_IMPLEMENTED if no combination of
implemented elements can satisfy it (e.g. it genuinely requires search,
filtering, wishlists, discount codes, or login) -- not merely because no
single element name matches the story's verb.

CALIBRATION EXAMPLE 1 (flagging a genuinely missing feature):
User story: "As a buyer, I want to search for products by name so I can find
what I need quickly."
Correct output:
{{"scenario_id": "future_search_product", "steps": [{{"action": "fill", "target": "NOT_IMPLEMENTED", "value": "product name", "expected": "search feature is not yet implemented"}}]}}
Note: even though "search-input" or "search-field" might sound like plausible
testid names, they do not exist in the app and must never be guessed.

CALIBRATION EXAMPLE 2 (decomposing a compound action into ALL implied real steps, in order):
User story: "As a buyer, I want to buy Diesel Fuel - 55 Gallon Drum, 3 times at once."
Correct output:
{{"scenario_id": "buy_diesel_fuel_55gal_x3", "steps": [
  {{"action": "navigate", "target": "product-catalog"}},
  {{"action": "click", "target": "category-tile", "value": "Fuel & Consumables"}},
  {{"action": "click", "target": "product-card", "value": "Diesel Fuel - 55 Gallon Drum"}},
  {{"action": "click", "target": "add-to-cart-button", "value": "Diesel Fuel - 55 Gallon Drum"}},
  {{"action": "fill", "target": "cart-item-quantity", "value": "3"}},
  {{"action": "click", "target": "checkout-submit-button"}}
]}}
Note: the category-tile click is now mandatory before any product-card click,
since products are not visible until their category is selected. Every part of
the story (the purchase, the quantity of 3, AND completing checkout) must show
up as a step, in this exact order -- do not stop after the first one or two
recognizable steps, and do not reorder or omit the category-tile step.
- "checkout-confirmation" (shown after a successful order, contains the created Order Id)
- "checkout-error" (shown if checkout fails)
- Account-based pricing IS implemented: different accounts (e.g. via testAccountId) see different prices for the same product from the resolved price book.

NOT IMPLEMENTED yet (do not invent selectors for these; there is still no login/authentication page in the current build):
- login / authentication as a specific account (test account context is set via a design attribute, not a login flow)

If the user story requires any NOT IMPLEMENTED element above, you must still output valid JSON, but:
- Prefix "scenario_id" with "future_"
- Add a step with "action": "assert", "target": "NOT_IMPLEMENTED", "expected": "<brief description of the missing feature this story depends on>"
- Do not invent a data-testid for anything not in the IMPLEMENTED list.
"""


def enforce_future_prefix(scenario: dict) -> dict:
    """Guarantee the future_ prefix on scenario_id whenever any step targets
    a not-yet-implemented feature, regardless of whether the LLM remembered
    to apply the prefix itself. Enforced in code, not just prompted."""
    has_not_implemented_step = any(
        step.get("target") == "NOT_IMPLEMENTED" for step in scenario.get("steps", [])
    )
    if has_not_implemented_step and not scenario["scenario_id"].startswith("future_"):
        scenario["scenario_id"] = f"future_{scenario['scenario_id']}"
    return scenario


def generate_scenario(user_story: str) -> dict:
    prompt = f"{SYSTEM_PROMPT}\n\nUser story: {user_story}\n\nJSON output:"

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
        },
    )
    response.raise_for_status()
    raw_text = response.json()["response"].strip()

    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()

    if not raw_text.startswith("{"):
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1:
            raw_text = raw_text[start:end + 1]

    try:
        scenario = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Generator returned invalid JSON: {e}\nRaw output:\n{raw_text}")

    try:
        validate(instance=scenario, schema=SCHEMA)
    except ValidationError as e:
        raise ValueError(f"Generated scenario failed schema validation: {e.message}")

    scenario = enforce_future_prefix(scenario)

    return scenario


def save_scenario(scenario: dict, output_dir: str = "scenarios") -> str:
    Path(output_dir).mkdir(exist_ok=True)
    out_path = Path(output_dir) / f"{scenario['scenario_id']}.json"
    out_path.write_text(json.dumps(scenario, indent=2))
    return str(out_path)


if __name__ == "__main__":
    story = input("Enter a user story: ")
    scenario = generate_scenario(story)
    path = save_scenario(scenario)
    print(f"Saved scenario to {path}")
    print(json.dumps(scenario, indent=2))
