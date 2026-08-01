from healer import build_repair_evidence, validate_repair_proposal
import json

visible_text_at_failure = """Visible text content:
Sfdclogo
Search Salesforce
Catalog Test
Catalog Test List
Close tab
More
GenWatt Diesel 1000kW
100000
Add to Cart
Test Widget A
100
Add to Cart
Checkout
Your cart is empty."""

step = {
    "action": "fill",
    "target": "search-input",
    "value": "product name",
    "status": "fail",
    "raw_tool_output": "Operation failed: page.waitForSelector: Timeout 30000ms exceeded.",
}

evidence = build_repair_evidence(step, visible_text_at_failure)

hallucinated_llm_result = {
    "has_confident_match": True,
    "proposed_testid_guess": "search-input-field",
    "reasoning": "The failed target's name suggests a search input field."
}

validated = validate_repair_proposal(evidence, hallucinated_llm_result)
print(json.dumps(validated, indent=2))
