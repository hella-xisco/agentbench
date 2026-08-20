#!/usr/bin/env python3
"""No-Action-Gate fuer den gestaffelten Varianz-Piloten (Pivot §12.4/§12.5).

Klassifiziert jede Trajektorie eines Run-Verzeichnisses in die vorregistrierten
Ausfallkategorien und prueft die No-Action-Rate gegen eine Schwelle:

  no_action   : 0 Assistant-Tool-Calls in der gesamten Trajektorie
                (Modell hat nie gehandelt — deterministischer Ausfallmodus,
                beobachtet im Skill-Gate 16.08. bei Pi x GLM)
  empty_patch : Tool-Calls vorhanden, aber leere Submission (versucht, kein Patch)
  acted       : Tool-Calls + nicht-leere Submission
  missing     : erwartete .traj.json fehlt (ExecutionFailed o. ae.) — zaehlt
                NICHT als no_action, wird aber getrennt ausgewiesen

Verwendung (im Batch-Treiber nach den ersten k Runs):
    python scripts/agentbench/run_harness/no_action_gate.py \
        --output_dir ~/runs/<run_id> --runs 0 1 --expected 10 --threshold 0.15

Exit-Code 0 = Gate GRUEN (Rate <= threshold), 1 = Gate ROT, 2 = zu wenige Daten.
"""

import argparse
import glob
import json
import os
import sys


def classify(traj_path: str) -> str:
    with open(traj_path) as f:
        data = json.load(f)

    messages = data.get("messages", []) or []
    tool_calls = 0
    for m in messages:
        if isinstance(m, dict) and m.get("role") == "assistant" and m.get("tool_calls"):
            tool_calls += len(m["tool_calls"])

    submission = (data.get("info", {}) or {}).get("submission") or ""
    if tool_calls == 0:
        return "no_action"
    if not submission.strip():
        return "empty_patch"
    return "acted"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output_dir", required=True, help="Run-Output-Verzeichnis (enthaelt agentbench/)")
    ap.add_argument("--runs", type=int, nargs="+", required=True, help="run_ids, die geprueft werden (z. B. 0 1)")
    ap.add_argument("--expected", type=int, required=True, help="erwartete Trajektorien pro run_id (= Task-Anzahl)")
    ap.add_argument("--threshold", type=float, default=0.15, help="max. tolerierte No-Action-Rate (default 0.15)")
    args = ap.parse_args()

    base = os.path.expanduser(args.output_dir)
    counts = {"no_action": 0, "empty_patch": 0, "acted": 0, "missing": 0}
    rows = []
    total_expected = args.expected * len(args.runs)

    for rid in args.runs:
        pattern = os.path.join(base, "agentbench", "**", f"run_{rid}", "*", "*.traj.json")
        trajs = sorted(glob.glob(pattern, recursive=True))
        counts["missing"] += max(0, args.expected - len(trajs))
        for t in trajs:
            cat = classify(t)
            counts[cat] += 1
            inst = os.path.basename(os.path.dirname(t))
            rows.append((rid, inst, cat))

    print(f"{'run':>4} {'instanz':<40} kategorie")
    for rid, inst, cat in rows:
        marker = "  <-- NO ACTION" if cat == "no_action" else ""
        print(f"{rid:>4} {inst:<40} {cat}{marker}")

    n_found = len(rows)
    print(f"\nTrajektorien: {n_found}/{total_expected}"
          f" | acted: {counts['acted']} | empty_patch: {counts['empty_patch']}"
          f" | no_action: {counts['no_action']} | missing: {counts['missing']}")

    if n_found < total_expected * 0.8:
        print("GATE: ZU WENIGE DATEN (>20 % der Trajektorien fehlen) — erst Ursache klaeren.")
        return 2

    rate = counts["no_action"] / n_found if n_found else 1.0
    verdict = "GRUEN" if rate <= args.threshold else "ROT"
    print(f"No-Action-Rate: {rate:.1%} (Schwelle {args.threshold:.0%}) -> GATE {verdict}")
    return 0 if verdict == "GRUEN" else 1


if __name__ == "__main__":
    sys.exit(main())
