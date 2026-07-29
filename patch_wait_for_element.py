path = "orchestrator.py"
with open(path) as f:
    src = f.read()

old = '''        check = await session.call_tool(
            "playwright_evaluate",
            {"script": f"document.querySelectorAll('{selector}').length"},
        )'''

if old not in src:
    raise SystemExit(
        "Exact block not found -- paste the current lines 41-59 of orchestrator.py "
        "so the patch can be adjusted to match your file exactly."
    )

new = '''        # NOTE: LWC renders with CLOSED native Shadow DOM by default, so
        # document.querySelectorAll(...) structurally cannot see component
        # internals from page-context JS (element.shadowRoot is null for
        # closed roots, even though the shadow root exists and is rendering).
        # playwright_get_visible_text reflects the rendered accessibility/text
        # tree and correctly crosses shadow boundaries, so we poll on that
        # instead of trying to pierce the DOM.
        check = await session.call_tool(
            "playwright_get_visible_text",
            {},
        )'''

src = src.replace(old, new, 1)
with open(path, "w") as f:
    f.write(src)
print("Patched wait_for_element() to poll visible text instead of DOM queries.")
