from healer import validate_repair_proposal
import json

# Case 1: previously correct proposal (should still pass) -- add-to-cart-btn-v2
evidence_1 = {
    "failed_target": "add-to-cart-btn-v2",
    "candidate_labels": ["Catalog Test", "GenWatt Diesel 1000kW", "Add to Cart"]
}
result_1 = {
    "has_confident_match": True,
    "proposed_testid_guess": "add-to-cart-button",
    "reasoning": "The visible label 'Add to Cart' matches."
}
print("--- Case 1: add-to-cart-btn-v2 -> add-to-cart-button ---")
print(json.dumps(validate_repair_proposal(evidence_1, result_1), indent=2))

# Case 2: previously correct proposal (should still pass) -- checkout-submit-btn-old
evidence_2 = {
    "failed_target": "checkout-submit-btn-old",
    "candidate_labels": ["Checkout", "Total: 100", "Submit Order"]
}
result_2 = {
    "has_confident_match": True,
    "proposed_testid_guess": "submit-order",
    "reasoning": "The visible label 'Submit Order' matches."
}
print("\n--- Case 2: checkout-submit-btn-old -> submit-order ---")
print(json.dumps(validate_repair_proposal(evidence_2, result_2), indent=2))
