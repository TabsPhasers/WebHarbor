#!/usr/bin/env python3
"""Craigslist--5: log in as alice, save a search named "Gaming chair watch" for furniture matching
'gaming chair' with a max price of $200. Deterministic-first: nav | DB after-state: a saved search
with this name, category_slug='furniture' and max_price=200 exists for alice (not in the initial
seed). The save-search form exposes the category and max price as editable fields, so all three
requirements are user-expressible."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, resolve_db, saved_searches_for, Judge, parse_args)
EMAIL = "alice.j@test.com"; NAME = "gaming chair watch"
def main():
    a = parse_args(); j = Judge('Craigslist--5', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    sa = saved_searches_for(after, EMAIL) or []
    si = saved_searches_for(init, EMAIL) or []
    names_a = [r[0].strip().lower() for r in sa]
    names_i = [r[0].strip().lower() for r in si]
    j.check("nav_save_search", navigated_any(t, ["/save-search", "/search"]), "expected the save-search flow")
    j.check("db_saved_search", NAME in names_a and NAME not in names_i,
            f"saved search '{NAME}' after={NAME in names_a} initial={NAME in names_i}")
    # saved_searches_for rows: (name, query_text, max_price, category_slug)
    match = [r for r in sa if r[0].strip().lower() == NAME]
    j.check("db_category_furniture", bool(match) and match[0][3] == "furniture",
            f"saved search must target the furniture category; row={match}")
    j.check("db_max_price_200", bool(match) and match[0][2] == 200,
            f"saved search must set max price 200; row={match}")
    j.emit()
if __name__ == "__main__":
    main()
