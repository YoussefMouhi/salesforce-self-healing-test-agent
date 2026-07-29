"""
generator.py
Self-Healing AI Test Automation Agent - Week 2 module

Turns a natural-language user story into a structured Playwright test scenario
(JSON) using the Claude API, then validates the output against
schemas/scenario_schema.json before it is considered usable downstream by
orchestrator.py (Week 3).

Usage:
    python generator.py --story-file data/user_stories.json --out data/generated_scenarios.json
    python generator.py --story "As a buyer, I want to add a product to my cart" --scenario-id cart-adhoc-001
"""

import argparse
import json
import os
import sys
from pathlib import Path

import anthropic
from jsonschema import validate, ValidationError

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "scenario_schema.json"
MODEL = "claude-sonnet-4-5"  # swap for the pinned model your [redacted] env uses

SYSTEM_PROMPT = """You are a test scenario generator for a Salesforce B2B Commerce
simulation built with custom Lightning Web Components.

Every interactive element in the app is annotated with a stable data-testid
attribute. Known testids you may reference:
- product-catalog (container)
- product-card (repeated per product)
- product-name, product-price (inside each product-card)
- add-to-cart-button
- cart-item, cart-quantity-input, remove-from-cart-button
- checkout-button, order-total, order-confirmation

Given a single user story, output ONE JSON object (and nothing else - no prose,
no markdown fences) that strictly matches this schema:

{schema}

Rules:
- steps must be concrete and executable: action, target (a CSS attribute
  selector against a data-testid, e.g. "[data-testid=\\"add-to-cart-button\\"]",
  or a URL for "navigate"), and value/expected where relevant.
- Prefer data-testid selectors over any other locator strategy.
- Include at least one "assert" step that verifies the outcome the story cares about.
- scenario_id should be a short kebab-case slug relevant to the story.
- Respond with raw JSON only.
"""


def load_schema() -> dict:
    with open(SCHEMA_PATH, "r") as f:
        return json.load(f)


def build_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY is not set. Export it before running generator.py.")
    return anthropic.Anthropic(api_key=api_key)


def generate_scenario(client: anthropic.Anthropic, schema: dict, story: str, journey: str = "") -> dict:
    """Call the LLM once for a single user story and return a validated scenario dict."""
    system = SYSTEM_PROMPT.format(schema=json.dumps(schema, indent=2))
    user_content = f"User story: {story}"
    if journey:
        user_content += f"\nJourney: {journey}"

    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )

    raw_text = "".join(block.text for block in response.content if block.type == "text").strip()
    raw_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        scenario = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON for story: {story!r}\nRaw output:\n{raw_text}") from e

    try:
        validate(instance=scenario, schema=schema)
    except ValidationError as e:
        raise ValueError(f"Generated scenario failed schema validation for story: {story!r}\n{e.message}") from e

    scenario["user_story"] = story
    return scenario


def generate_from_file(client: anthropic.Anthropic, schema: dict, story_file: Path) -> list[dict]:
    with open(story_file, "r") as f:
        stories = json.load(f)

    scenarios = []
    failures = []
    for entry in stories:
        story = entry["story"]
        journey = entry.get("journey", "")
        print(f"Generating scenario for {entry['id']}: {story[:60]}...")
        try:
            scenario = generate_scenario(client, schema, story, journey)
            scenario["source_id"] = entry["id"]
            scenarios.append(scenario)
        except ValueError as e:
            print(f"  FAILED: {e}", file=sys.stderr)
            failures.append({"id": entry["id"], "error": str(e)})

    if failures:
        print(f"\n{len(failures)}/{len(stories)} stories failed generation. See stderr above.")
    else:
        print(f"\nAll {len(stories)} stories generated and validated successfully.")

    return scenarios


def main():
    parser = argparse.ArgumentParser(description="Generate Playwright test scenarios from user stories.")
    parser.add_argument("--story", type=str, help="A single ad-hoc user story to generate.")
    parser.add_argument("--scenario-id", type=str, help="Optional id hint for --story mode.")
    parser.add_argument("--story-file", type=Path, help="Path to a JSON file of user stories (see data/user_stories.json).")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "generated_scenarios.json")
    args = parser.parse_args()

    schema = load_schema()
    client = build_client()

    if args.story:
        scenario = generate_scenario(client, schema, args.story)
        print(json.dumps(scenario, indent=2))
        return

    story_file = args.story_file or (ROOT / "data" / "user_stories.json")
    scenarios = generate_from_file(client, schema, story_file)

    with open(args.out, "w") as f:
        json.dump(scenarios, f, indent=2)
    print(f"Wrote {len(scenarios)} scenarios to {args.out}")


if __name__ == "__main__":
    main()