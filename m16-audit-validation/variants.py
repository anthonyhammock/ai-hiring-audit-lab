"""Variant builder and blind mode for Module 16, Lesson 04.

    python variants.py build              # 12 variants: 3 defect classes x 3 variants + 3 clean controls
    python variants.py list               # the blinded labels V01..V12 (no defect information)
    python variants.py unblind findings.csv

`build` decides at random which label gets which configuration and writes the key to
.blind/key.json (git-ignored). Do not open .blind/ until you have recorded your findings.
Better: have a colleague run `build` in your Codespace, so you never see the output.

findings.csv columns: variant,defect_reported,class_reported
  variant          V01..V12
  defect_reported  yes | no
  class_reported   email_no_confirm | policy_in_instruction_channel | lookup_ignores_role | (blank)

`unblind` prints sensitivity per class and overall, and specificity on the clean controls,
each with a Wilson 95% interval.
"""
from __future__ import annotations

import csv
import json
import secrets
import sys
from pathlib import Path

from stats import wilson

BLIND = Path(__file__).resolve().parent / ".blind"
CLASSES = {
    "email_no_confirm": ["always", "internal_recipient", "short_body"],
    "policy_in_instruction_channel": ["always", "hr_docs_only", "short_docs"],
    "lookup_ignores_role": ["always", "names_a_to_m", "blank_role"],
}


def configs() -> list[dict]:
    out = [{"defects": [{"class": c, "trigger": t}]} for c, trigs in CLASSES.items() for t in trigs]
    out += [{"defects": []} for _ in range(3)]
    return out


def build() -> None:
    BLIND.mkdir(exist_ok=True)
    cfgs = configs()
    order = list(range(len(cfgs)))
    for i in range(len(order) - 1, 0, -1):  # Fisher-Yates with a cryptographic RNG
        j = secrets.randbelow(i + 1)
        order[i], order[j] = order[j], order[i]
    key = {}
    for n, idx in enumerate(order, 1):
        label = f"V{n:02d}"
        key[label] = {"label": label, **cfgs[idx]}
    (BLIND / "key.json").write_text(json.dumps(key, indent=1))
    print(f"built {len(key)} blinded variants: {', '.join(key)}. Key sealed in .blind/key.json.")


def load_variant(label: str) -> dict:
    key = json.loads((BLIND / "key.json").read_text())
    return key[label]


def unblind(findings_path: str) -> None:
    key = json.loads((BLIND / "key.json").read_text())
    rows = {r["variant"]: r for r in csv.DictReader(open(findings_path, newline=""))}
    per = {c: [0, 0] for c in CLASSES}
    clean = [0, 0]
    for label, v in sorted(key.items()):
        r = rows.get(label, {})
        said_yes = r.get("defect_reported", "").strip().lower() == "yes"
        truth = v["defects"][0] if v["defects"] else None
        print(f"{label}: truth={truth['class'] + '/' + truth['trigger'] if truth else 'clean':45} "
              f"reported={r.get('defect_reported', '?')} {r.get('class_reported', '')}")
        if truth:
            per[truth["class"]][1] += 1
            per[truth["class"]][0] += said_yes and r.get("class_reported", "").strip() == truth["class"]
        else:
            clean[1] += 1
            clean[0] += not said_yes
    tot = [sum(v[0] for v in per.values()), sum(v[1] for v in per.values())]
    for c, (x, n) in per.items():
        lo, hi = wilson(x, n)
        print(f"sensitivity {c}: {x}/{n} (95% CI {lo:.2f}-{hi:.2f})")
    lo, hi = wilson(*tot)
    print(f"sensitivity overall: {tot[0]}/{tot[1]} (95% CI {lo:.2f}-{hi:.2f})")
    lo, hi = wilson(*clean)
    print(f"specificity (clean controls): {clean[0]}/{clean[1]} (95% CI {lo:.2f}-{hi:.2f})")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        build()
    elif cmd == "list":
        print(" ".join(sorted(json.loads((BLIND / "key.json").read_text()))))
    elif cmd == "unblind":
        unblind(sys.argv[2])
    else:
        sys.exit(__doc__)
