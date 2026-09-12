#!/usr/bin/env python3
"""Healthline--6: sign in as alice, report how many articles are in the saved list.
GT: 5 (pre-seeded). Deterministic: nav /saved + answer count cross-checked against the DB.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_any, number_mentioned,
                        resolve_db, saved_articles_for, Judge, parse_args)

EMAIL = "alice.j@test.com"

def main():
    a = parse_args(); j = Judge('Healthline--6', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    saved = saved_articles_for(init, EMAIL)
    # the saved list is shown on both /saved and the /account page — accept either
    j.check("nav_saved", navigated_any(t, ["/saved", "/account"]),
            "expected the saved articles page or the account page")
    # a missing/unreadable initial DB is an infrastructure failure, never a zero count
    j.check("answer_count", saved is not None and number_mentioned(fa, len(saved)),
            f"expected saved count from DB; db_available={saved is not None}; final={fa!r}")
    j.emit()

if __name__ == "__main__":
    main()
