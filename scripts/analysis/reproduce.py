"""Reproduce accepted analyses and thesis assets in a new directory only."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def commands(output: Path, assets_only: bool, render: bool) -> list[list[str]]:
    configs = ROOT / "scripts/analysis/configs"
    results = {}
    steps = []
    for name in ("vp_glm", "vp_qwen", "main_glm", "main_qwen"):
        config = json.loads((configs / f"{name}.json").read_text())
        pilot = name.startswith("vp_")
        accepted = ROOT / config["run_directory"] / "analysis" / ("variance-pilot-v2" if pilot else "statistics-v3")
        results[name] = accepted if assets_only else output / "analyses" / name
        if not assets_only:
            module = "variance_pilot" if pilot else "main_run"
            steps.append([sys.executable, "-m", f"thesis_analysis.{module}", "--config", str(configs / f"{name}.json"), "--output-dir", str(results[name])])
    tables, figures = output / "tables", output / "figures"
    base = [sys.executable, "-m", "thesis_analysis.reporting"]
    pilot_args = ["--glm-pilot-output", str(results["vp_glm"]), "--qwen-pilot-output", str(results["vp_qwen"])]
    main_args = ["--glm-main-output", str(results["main_glm"]), "--qwen-main-output", str(results["main_qwen"])]
    palette = ["--palette", str(ROOT / "figures/palette.json")]
    rendering = ["--render"] if render else []
    statements = ROOT / "categorized-data-set/coding/statements.csv"
    if not statements.exists():
        statements = ROOT / "benchmark/categorized-data-set/coding/statements.csv"
    steps.extend([
        base + ["pilot-tables"] + pilot_args + ["--glm-config", str(configs / "vp_glm.json"), "--output-dir", str(tables)],
        base + ["pilot-figures"] + pilot_args + palette + ["--output-dir", str(figures)] + rendering,
        base + ["material-categorization", "--statements", str(statements), "--output-dir", str(tables)],
        base + ["main-overview"] + main_args + ["--output-dir", str(tables)],
        base + ["main-results"] + main_args + palette + ["--table-output-dir", str(tables), "--figure-output-dir", str(figures)] + rendering,
    ])
    return steps


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--assets-only", action="store_true", help="Use accepted analyses, but still read recorded trajectories for behaviour assets")
    parser.add_argument("--render", action="store_true", help="Requires rsvg-convert; additionally produce PDF/PNG")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        raise SystemExit("Output directory already exists; choose a new directory")
    steps = commands(output, args.assets_only, args.render)
    output.mkdir(parents=True, exist_ok=False)
    for step in steps:
        subprocess.run(step, cwd=ROOT, check=True)
    print(f"Reproduced in {output}; accepted outputs unchanged")


if __name__ == "__main__":
    main()
