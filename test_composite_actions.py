"""
test_composite_actions.py -- regression test for the COMPOSITE ACTIONS
prompt rule added to generator.py's SYSTEM_PROMPT (patch_composite_actions.py).

Guards against two failure modes observed before the fix:
1. Compound/colloquial stories ("buy X, N times") being incorrectly flagged
   future_/NOT_IMPLEMENTED even though achievable via real implemented steps.
2. Silent truncation -- dropping the quantity step or the checkout step, or
   emitting them out of order (add-to-cart-button must precede
   cart-item-quantity).
"""

from generator import generate_scenario

REQUIRED_TARGETS_IN_ORDER = [
    "product-catalog",
    "product-card",
    "add-to-cart-button",
    "cart-item-quantity",
    "checkout-submit-button",
]

CASES = [
    "As a buyer, I want to buy Portable5000, 3 times at once.",
    "As a buyer, I want to order 2 units of Portable5000.",
    "As a buyer, I want to purchase 4 Portable5000 items.",
]


def check(story: str) -> None:
    scenario = generate_scenario(story)
    scenario_id = scenario["scenario_id"]
    targets = [step["target"] for step in scenario["steps"]]

    assert not scenario_id.startswith("future_"), (
        f"FAIL [{story!r}]: incorrectly flagged future_/NOT_IMPLEMENTED "
        f"(scenario_id={scenario_id!r}, steps={targets})"
    )

    # every required target must appear, in the required relative order
    positions = []
    for required in REQUIRED_TARGETS_IN_ORDER:
        assert required in targets, (
            f"FAIL [{story!r}]: missing required step target {required!r} "
            f"(got targets={targets})"
        )
        positions.append(targets.index(required))

    assert positions == sorted(positions), (
        f"FAIL [{story!r}]: required steps out of order "
        f"(got targets={targets}, expected order={REQUIRED_TARGETS_IN_ORDER})"
    )

    print(f"PASS [{story!r}] -> scenario_id={scenario_id!r}")


if __name__ == "__main__":
    for story in CASES:
        check(story)
    print(f"\nAll {len(CASES)} composite-action cases passed.")
