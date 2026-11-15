"""Referee self-test — fail-closed. Every case must classify as expected.

Writes a measured receipt to selftest-receipt.json and exits nonzero on
any mismatch. Run: python selftest.py
"""
import json
import sys
import time
from pathlib import Path

import referee
import rewards
import probes

CASES = [
    ("accepted-horus-fast", "TH_V18_04-egyptian-horus",
     probes.FORMALIZED["TH_V18_04-egyptian-horus"][0],
     "decide", "fast", referee.V.PROOF_ACCEPTED),
    ("accepted-horus-lake", "TH_V18_04-egyptian-horus",
     probes.FORMALIZED["TH_V18_04-egyptian-horus"][0],
     "decide", "lake", referee.V.PROOF_ACCEPTED),
    ("bluff-sorry", "TH_V18_04-egyptian-horus",
     probes.FORMALIZED["TH_V18_04-egyptian-horus"][0],
     "sorry", "fast", referee.V.SORRY_PRESENT),
    ("bluff-build-error", "TH_V18_04-egyptian-horus",
     probes.FORMALIZED["TH_V18_04-egyptian-horus"][0],
     "exact 64", "fast", referee.V.BUILD_ERROR),
    ("abstain-conjecture", probes.conjecture_anchor_id(),
     "theorem probe_conjecture : True",
     "--ABSTAIN conjecture-class anchor: no proof claimed", "fast", referee.V.ABSTAIN),
    ("axiom-smuggle", "TH_V18_03-kraft",
     probes.FORMALIZED["TH_V18_03-kraft"][0],
     "axiom cheat : 4 + 2 + 1 + 1 = 8\nrw [cheat]", "fast", referee.V.AXIOM_SMUGGLED),
]


def main():
    receipt = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "cases": [], "ok": True}
    for name, pid, stmt, attempt, mode, expected in CASES:
        r = referee.classify(pid, stmt, attempt, mode=mode)
        cls = probes.probe_class(pid)
        rw = rewards.reward(r["verdict"], cls)
        ok = r["verdict"] == expected
        receipt["cases"].append({"case": name, "expected": expected,
                                 "got": r["verdict"], "ok": ok,
                                 "reward": rw, "elapsed_s": r["elapsed_s"],
                                 "build_exit_code": r["build_exit_code"],
                                 "axioms": r["axioms"],
                                 "build_tail": r["build_tail"]})
        if not ok:
            receipt["ok"] = False
    receipt["reward_table_check"] = {
        "accepted": rewards.reward("PROOF_ACCEPTED", "SYMBOLIC") == 1.0,
        "abstain_conjecture": rewards.reward("ABSTAIN", "CONJECTURE") == 0.5,
        "abstain_symbolic": rewards.reward("ABSTAIN", "SYMBOLIC") == 0.1,
        "bluff_sorry": rewards.reward("SORRY_PRESENT", "SYMBOLIC") == 0.0,
        "smuggle": rewards.reward("AXIOM_SMUGGLED", "SYMBOLIC") == 0.0,
    }
    if not all(receipt["reward_table_check"].values()):
        receipt["ok"] = False
    Path(__file__).resolve().parent.joinpath("selftest-receipt.json").write_text(
        json.dumps(receipt, indent=1) + "\n", encoding="utf-8")
    for c in receipt["cases"]:
        print(("PASS " if c["ok"] else "FAIL ") + c["case"] + " -> " + c["got"]
              + " r=" + str(c["reward"]))
    print("SELFTEST", "OK" if receipt["ok"] else "FAILED")
    sys.exit(0 if receipt["ok"] else 1)


if __name__ == "__main__":
    main()
