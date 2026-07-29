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
