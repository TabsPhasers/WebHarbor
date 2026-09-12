#!/usr/bin/env python3
"""Healthline--15: atorvastatin drug page — is grapefruit juice listed as an interaction?
GT: Yes, grapefruit juice IS listed as an interaction.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, contains_any,
                        llm_text_match, Judge, parse_args)

def main():
    a = parse_args(); j = Judge('Healthline--15', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_drug", navigated_to(t, "/drug/atorvastatin"), "expected the atorvastatin drug page")
    j.check("answer_grapefruit", contains_any(fa, ["grapefruit"]),
            f"expected mention of grapefruit; final={fa!r}")
    # answer must affirm it IS an interaction, not deny it
    affirm = contains_any(fa, ["yes", "is listed", "listed as", "is an interaction", "interacts"])
    negate = contains_any(fa, ["not", "no ", "no,", "isn't", "without", "absent", "none",
                               "does not", "doesn't"])
    j.check("answer_affirms", affirm and not negate,
            f"answer must affirm grapefruit juice IS an interaction; final={fa!r}")
    ok, ev = llm_text_match(fa, "yes — grapefruit juice is listed as an interaction to be aware of for atorvastatin",
                            "Is grapefruit juice listed as an interaction on the atorvastatin page?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
