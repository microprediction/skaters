"""Check every number in paper.md against constants.py. Exits non-zero on drift.

    python papers/stronger-benchmark/verify_paper.py

The paper's tables are markdown, so they are typed. This closes that gap: the
prose is only trustworthy if a script re-derives each cell from the store and
compares. A referee runs this instead of taking the Reproducibility section's
word for it.
"""
from __future__ import annotations
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import constants  # noqa: E402

PAPER = os.path.join(HERE, "paper.md")
LABEL_TO_KEY = {
    "daily, economic": "daily:econ",
    "daily, price/returns": "daily:price",
    "weekly, economic": "weekly:econ",
    "monthly, economic": "monthly:econ",
    "M4-hourly, seasonal": "m4-hourly:econ",
}
MINUS = "−"


def _num(s):
    return float(s.replace(",", "").replace(MINUS, "-").replace("%", "").strip())


def parse_tables(text):
    """Yield (label, n, win, draw, loss, dLL, loss_rate) for every results row."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 5 or cells[0] not in LABEL_TO_KEY:
            continue
        wdl = [p.strip() for p in cells[2].split("/")]
        if len(wdl) != 3:
            continue
        out.append((cells[0], _num(cells[1]), int(_num(wdl[0])), int(_num(wdl[1])),
                    int(_num(wdl[2])), _num(cells[3]), _num(cells[4])))
    return out


def main():
    text = open(PAPER).read()
    rows = parse_tables(text)
    if len(rows) != 10:
        print(f"FAIL: expected 10 result rows (5 raw + 5 wrapped), found {len(rows)}")
        for r in rows:
            print("   parsed:", r)
        return 1

    h2h = constants.head_to_head()
    noz = constants.nozzle()
    bad = []

    for i, (label, n, w, d, l, dll, lr) in enumerate(rows):
        rec = h2h[LABEL_TO_KEY[label]]
        wrapped = i >= 5
        p = "wrapped_" if wrapped else ""
        exp = (rec[p + "n_series"], rec[p + "win"], rec[p + "draw"], rec[p + "loss"],
               rec[p + "med_dLL"], rec[p + "loss_rate"] * 100)
        tag = "wrapped" if wrapped else "raw"
        if (n, w, d, l) != exp[:4]:
            bad.append(f"{tag:8s} {label:22s} counts: paper {(n,w,d,l)} vs store {exp[:4]}")
        if abs(dll - round(exp[4], 3)) > 5e-4:
            bad.append(f"{tag:8s} {label:22s} med_dLL: paper {dll} vs store {exp[4]:.4f}")
        if abs(lr - exp[5]) > 0.05:
            bad.append(f"{tag:8s} {label:22s} loss_rate: paper {lr}% vs store {exp[5]:.2f}%")

    checks = [
        ("held-out test points", noz["n_points"], 3200),
        ("worst nozzle mean logpdf", round(min(noz["methods"].values()), 3), -0.373),
        ("best nozzle mean logpdf", round(max(noz["methods"].values()), 3), 2.104),
        ("mean per-point spread", round(noz["mean_spread"], 2), 3.13),
        ("local vs grid", round(abs(noz["local_vs_grid"]), 2), 0.62),
    ]
    for name, store_val, paper_val in checks:
        if abs(store_val - paper_val) > 1e-6:
            bad.append(f"prose    {name}: paper {paper_val} vs store {store_val}")

    claimed = re.search(r"falls by as much as\s+([\w-]+)\s+points", text)
    drop = round(constants.derived(h2h, noz)["max_loss_rate_drop"] * 100)
    words = {39: "thirty-nine"}
    if claimed and claimed.group(1) != words.get(drop, str(drop)):
        bad.append(f"prose    max loss-rate drop: paper '{claimed.group(1)}' vs store {drop}")

    if bad:
        print("DRIFT DETECTED between paper.md and the store:\n")
        for b in bad:
            print("  " + b)
        return 1
    print(f"OK: {len(rows)} table rows and {len(checks) + 1} prose figures match the store.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
