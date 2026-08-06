"""
patch_composite_actions.py -- one-off patch adding a COMPOSITE ACTIONS rule
and a second calibration example to generator.py's SYSTEM_PROMPT.
"""

from pathlib import Path

PATH = Path("generator.py")

OLD = '''CALIBRATION EXAMPLE (follow this pattern exactly):
User story: "As a buyer, I want to search for products by name so I can find
what I need quickly."
Correct output:
{{"scenario_id": "future_search_product", "steps": [{{"action": "fill", "target": "NOT_IMPLEMENTED", "value": "product name", "expected": "search feature is not yet implemented"}}]}}
Note: even though "search-input" or "search-field" might sound like plausible
testid names, they do not exist in the app and must never be guessed.'''

NEW = '''COMPOSITE ACTIONS -- before concluding a story is NOT_IMPLEMENTED, check whether
it can be satisfied by CHAINING two or more IMPLEMENTED elements together, even
if the story uses a single colloquial verb (e.g. "buy", "order", "purchase",
"get") that has no single matching testid of its own. These verbs almost always
map to the real multi-step flow, IN THIS EXACT ORDER: navigate to
product-catalog -> click the product-card -> click add-to-cart-button -> (if a
quantity or repeat count is mentioned) fill cart-item-quantity -> click
checkout-submit-button. Quantity can only be set on an item already in the
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
User story: "As a buyer, I want to buy Portable5000, 3 times at once."
Correct output:
{{"scenario_id": "buy_portable5000_x3", "steps": [
  {{"action": "navigate", "target": "product-catalog"}},
  {{"action": "click", "target": "product-card", "value": "Portable5000"}},
  {{"action": "click", "target": "add-to-cart-button"}},
  {{"action": "fill", "target": "cart-item-quantity", "value": "3"}},
  {{"action": "click", "target": "checkout-submit-button"}}
]}}
Note: "buy ... 3 times at once" has no single matching testid, but it is fully
achievable by chaining real implemented elements, in the correct real-world
order. Every part of the story (the purchase, AND the quantity of 3, AND
completing checkout) must show up as a step, and add-to-cart-button must come
BEFORE cart-item-quantity, never after -- do not stop after the first one or
two recognizable steps, and do not reorder them.'''


def main():
    text = PATH.read_text()
    if NEW in text:
        print("Already patched -- no changes made.")
        return
    if OLD not in text:
        raise SystemExit(
            "OLD block not found verbatim in generator.py -- file has likely "
            "changed since this patch was written. Aborting without changes; "
            "inspect generator.py manually before patching."
        )
    text = text.replace(OLD, NEW)
    PATH.write_text(text)
    print(f"Patched {PATH}: added COMPOSITE ACTIONS rule + CALIBRATION EXAMPLE 2.")


if __name__ == "__main__":
    main()
