path = "healer.py"
with open(path) as f:
    src = f.read()

old = '''def validate_repair_proposal(evidence: dict, llm_result: dict) -> dict:
    """
    Deterministic sanity checks on the LLM's proposal, run regardless of
    the model's own has_confident_match/confidence claims -- those have
    been observed to be unreliable (e.g. llama3.1:8b proposing the exact
    same testid that already failed, with non-sequitur reasoning).

    Returns llm_result with has_confident_match forced to False and a
    rejection reason appended if any check fails. This function is the
    real gate; the model\\'s self-reported confidence is advisory only.
    """
    if not llm_result.get("has_confident_match"):
        return llm_result

    guess = llm_result.get("proposed_testid_guess")
    original = evidence.get("failed_target")

    if not guess:
        llm_result["has_confident_match"] = False
        llm_result["reasoning"] += " [REJECTED: has_confident_match=true but no guess provided]"
        return llm_result

    if guess.strip() == (original or "").strip():
        llm_result["has_confident_match"] = False
        llm_result["reasoning"] += (
            f" [REJECTED: proposed testid '{guess}' is identical to the "
            f"original failed target -- not a repair, likely model overconfidence]"
        )
        return llm_result

    return llm_result'''

new = '''def validate_repair_proposal(evidence: dict, llm_result: dict) -> dict:
    """
    Deterministic sanity checks on the LLM's proposal, run regardless of
    the model's own has_confident_match/confidence claims. Two distinct
    failure modes have been observed live:
      1. Proposing the exact same testid that already failed (circular).
      2. Inventing a plausible-sounding testid derived purely from the
         ORIGINAL FAILED TARGET NAME, with no grounding in the real page
         evidence -- observed live: for a genuinely nonexistent
         "search-input" feature, the model proposed "search-input-field"
         with high confidence, despite zero search-related content in the
         real page evidence. This is a hallucination triggered by the
         target name itself, and is the most dangerous failure mode for
         an auto-apply system.

    Returns llm_result with has_confident_match forced to False and a
    rejection reason appended if any check fails. This function is the
    real gate; the model's self-reported confidence is advisory only.
    """
    if not llm_result.get("has_confident_match"):
        return llm_result

    guess = llm_result.get("proposed_testid_guess")
    original = evidence.get("failed_target")

    if not guess:
        llm_result["has_confident_match"] = False
        llm_result["reasoning"] += " [REJECTED: has_confident_match=true but no guess provided]"
        return llm_result

    if guess.strip() == (original or "").strip():
        llm_result["has_confident_match"] = False
        llm_result["reasoning"] += (
            f" [REJECTED: proposed testid '{guess}' is identical to the "
            f"original failed target -- not a repair, likely model overconfidence]"
        )
        return llm_result

    candidate_text = " ".join(evidence.get("candidate_labels", [])).lower()
    guess_words = [w for w in re.split(r"[-_\\s]+", guess.lower()) if len(w) > 2]
    grounded = any(word in candidate_text for word in guess_words)

    if not grounded:
        llm_result["has_confident_match"] = False
        llm_result["reasoning"] += (
            f" [REJECTED: proposed testid '{guess}' has no traceable connection "
            f"to any candidate_labels evidence -- likely hallucinated from the "
            f"original target's name rather than derived from real page content]"
        )
        return llm_result

    return llm_result'''

if old not in src:
    raise SystemExit("Still no exact match -- pasting diff context needed.")
src = src.replace(old, new, 1)
with open(path, "w") as f:
    f.write(src)
print("Patched validate_repair_proposal() with evidence-grounding check.")
