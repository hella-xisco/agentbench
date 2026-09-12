#!/usr/bin/env python3
"""Count the coded statements and list the changes between two codings.

    python3 count_m1c.py ../coding/statements.csv
    python3 count_m1c.py ../coding/statements.csv --kappa ../coding/first-pass.csv

Prints the bucket distribution per repository and the wording-status counts.
With --kappa it matches both files over the statement id, reports the raw
agreement over the shared ids and lists every statement whose bucket differs.
"""
import argparse
import csv
from collections import Counter, OrderedDict
from pathlib import Path

BUCKETS = ("P", "D", "N", "M")


def load(path: Path) -> "OrderedDict[str, dict]":
    with path.open(encoding="utf-8", newline="") as f:
        return OrderedDict((r["id"], r) for r in csv.DictReader(f))


def report(rows) -> None:
    per, words = OrderedDict(), Counter()
    for r in rows.values():
        per.setdefault(r.get("repo", "?"), Counter())[r["bucket"]] += 1
        words[r.get("wording", "").split(" (")[0]] += 1
    total = Counter()
    print(f"{'repo':<30}{'n':>5}{'P':>5}{'D':>5}{'N':>5}{'M':>5}{'excluded':>10}")
    for repo, c in sorted(per.items(), key=lambda kv: -sum(kv[1].values())):
        n = sum(c.values())
        print(f"{repo:<30}{n:5}{c['P']:5}{c['D']:5}{c['N']:5}{c['M']:5}"
              f"{round(100 * (c['N'] + c['M']) / n):9} %")
        total += c
    n = sum(total.values())
    print(f"{'total':<30}{n:5}{total['P']:5}{total['D']:5}{total['N']:5}{total['M']:5}"
          f"{round(100 * (total['N'] + total['M']) / n):9} %")
    if words:
        print("wording:", dict(words.most_common()))


def compare(a, b, name_a, name_b) -> None:
    ids = [i for i in a if i in b]
    if not ids:
        raise SystemExit("no shared statement ids")
    same = sum(a[i]["bucket"] == b[i]["bucket"] for i in ids)
    print(f"\nshared ids: {len(ids)}   same bucket: {same}   changed: {len(ids) - same}")
    for i in ids:
        if a[i]["bucket"] != b[i]["bucket"]:
            print(f"  {i}: {b[i]['bucket']} -> {a[i]['bucket']}")
    extra = [i for i in a if i not in b]
    if extra:
        print(f"only in {name_a} (split in the review): {', '.join(extra)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("file", type=Path)
    ap.add_argument("--kappa", metavar="FIRST_PASS", type=Path,
                    help="compare against the first-pass coding")
    args = ap.parse_args()
    rows = load(args.file)
    report(rows)
    if args.kappa:
        compare(rows, load(args.kappa), args.file.name, args.kappa.name)
