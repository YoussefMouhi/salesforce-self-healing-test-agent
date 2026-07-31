from healer import classify_failure

test_cases = [
    {
        "name": "real failure: search-input never appeared",
        "step_result": {
            "action": "fill",
            "target": "search-input",
            "status": "fail",
            "raw_tool_output": "Operation failed: page.waitForSelector: Timeout 30000ms exceeded.\nCall log:\n  - waiting for locator('[data-testid=\"search-input\"]') to be visible\n"
        }
    },
    {
        "name": "synthetic: disabled button",
        "step_result": {
            "action": "click",
            "target": "checkout-submit-button",
            "status": "fail",
            "raw_tool_output": "Operation failed: element is not enabled"
        }
    },
    {
        "name": "synthetic: assertion mismatch",
        "step_result": {
            "action": "assert",
            "target": "checkout-confirmation",
            "status": "fail",
            "detail": "found_in_visible_text=False"
        }
    },
]

for case in test_cases:
    result = classify_failure(case["step_result"])
    print(f"--- {case['name']} ---")
    print(result)
    print()
