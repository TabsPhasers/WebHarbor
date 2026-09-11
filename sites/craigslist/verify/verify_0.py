#!/usr/bin/env python3
"""Craigslist--0: log in as alice, search furniture east bay for a chair under $100 with adjustable
arms, open it, and save it. Target = 'Ergonomic task chair' (id 1, $85, arms: adjustable).

Verified by the initial->after delta: id 1 must be ABSENT from alice's saved listings in the
initial snapshot (the pre-seeded saved chair is the Black office chair, id 2) and PRESENT after
the run. A no-op / visit-only run therefore fails on the saved-state check.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, opened_listing, navigated_any, resolve_db, saved_listing_ids,
                        Judge, parse_args)
EMAIL = "alice.j@test.com"; LID = 1
def main():
    a = parse_args(); j = Judge('Craigslist--0', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    j.check("nav_listing_or_save", opened_listing(t, LID) or navigated_any(t, [f"/listing/{LID}/save"]),
            "expected the adjustable-arms chair (id 1) / a save action")
    sa = saved_listing_ids(after, EMAIL) or []
    si = saved_listing_ids(init, EMAIL) or []
    j.check("db_not_saved_initially", si is not None and LID not in si,
            f"chair id {LID} must NOT be pre-saved; initial saved={si}")
    j.check("db_saved_after_run", LID in sa,
            f"chair id {LID} must be added to alice's saved listings by this run; after={sa}")
    j.emit()
if __name__ == "__main__":
    main()
