#!/usr/bin/env python3
"""Craigslist--3: log in as alice, find the 2011 Honda Accord EX-L under $7000 with clean title
(id 15), open it, and save it.

The pre-seeded saved Accord is the 2006 EX sedan (id 13, the item task 13 removes); the 2011 EX-L
is a distinct, non-pre-saved listing, so the save is verifiable via the initial->after delta:
id 15 must be ABSENT initially and PRESENT after. The 2006 EX is a deliberate near-miss distractor
(also an Accord, also clean, also under $7000) - saving id 13 instead fails.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, opened_listing, navigated_any, resolve_db, saved_listing_ids,
                        Judge, parse_args)
EMAIL = "alice.j@test.com"; LID = 15; DISTRACTOR = 13
def main():
    a = parse_args(); j = Judge('Craigslist--3', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    j.check("nav_listing_or_save", opened_listing(t, LID) or navigated_any(t, [f"/listing/{LID}/save"]),
            "expected the 2011 Honda Accord EX-L (id 15) / a save action")
    sa = saved_listing_ids(after, EMAIL) or []
    si = saved_listing_ids(init, EMAIL) or []
    j.check("db_not_saved_initially", si is not None and LID not in si,
            f"Accord EX-L id {LID} must NOT be pre-saved; initial saved={si}")
    j.check("db_saved_after_run", LID in sa,
            f"Accord EX-L id {LID} must be added to alice's saved listings; after={sa}")
    j.check("db_distractor_not_added", DISTRACTOR in si and DISTRACTOR in sa,
            f"the pre-saved 2006 Accord EX (id {DISTRACTOR}) must remain untouched (it is not this task's target)")
    j.emit()
if __name__ == "__main__":
    main()
