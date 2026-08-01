"""
review_fixes.py -- human review tool for proposed_fixes.

Lists pending proposals and lets the reviewer approve or reject each one,
with an optional note. This is the final gate before any fix could ever
be applied -- nothing in this project auto-applies a proposed_testid_guess
without a human explicitly approving it here.
"""

import sqlite3
import sys

DB_PATH = "test_runs.db"


def list_pending():
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT fix_id, run_id, step_index, original_target, proposed_testid_guess, "
            "llm_has_confident_match, llm_reasoning, classifier_category, "
            "classifier_confidence, created_at "
            "FROM proposed_fixes WHERE status = 'pending' ORDER BY fix_id ASC"
        ).fetchall()
        return rows
    finally:
        conn.close()


def set_status(fix_id: int, status: str, note: str = ""):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE proposed_fixes SET status = ?, reviewer_note = ?, reviewed_at = datetime('now') "
            "WHERE fix_id = ?",
            (status, note, fix_id),
        )
        conn.commit()
    finally:
        conn.close()


def main():
    rows = list_pending()
    if not rows:
        print("No pending proposals to review.")
        return

    print(f"\n{len(rows)} pending proposal(s):\n")

    for row in rows:
        (fix_id, run_id, step_index, original_target, proposed_guess,
         llm_confident, llm_reasoning, category, confidence, created_at) = row

        print("=" * 70)
        print(f"fix_id={fix_id}  run_id={run_id}  step_index={step_index}  created_at={created_at}")
        print(f"Original (failed) target : {original_target}")
        print(f"Proposed replacement     : {proposed_guess}")
        print(f"LLM has_confident_match  : {bool(llm_confident)}")
        print(f"Classifier category      : {category} (confidence={confidence})")
        print(f"LLM reasoning            : {llm_reasoning}")
        print()

        if not llm_confident:
            print("NOTE: the validation gate already rejected this proposal "
                  "(has_confident_match=False). It is shown here for visibility "
                  "only -- approving it does nothing useful, since there is no "
                  "trustworthy replacement selector to apply.")

        answer = input("Approve this fix? [y/n/skip]: ").strip().lower()
        if answer == "y":
            note = input("Optional note: ").strip()
            set_status(fix_id, "approved", note)
            print(f"-> fix_id={fix_id} marked APPROVED.\n")
        elif answer == "n":
            note = input("Optional reason: ").strip()
            set_status(fix_id, "rejected", note)
            print(f"-> fix_id={fix_id} marked REJECTED.\n")
        else:
            print(f"-> fix_id={fix_id} left pending, skipped.\n")


if __name__ == "__main__":
    main()
