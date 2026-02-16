#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

# Allow direct execution from the repository without installation.
REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
for candidate in (SRC_ROOT, REPO_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from agentbench.utils.trace import Trace


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load an AgentBench trace JSON file and render HTML with Trace.visualize()."
    )
    parser.add_argument(
        "trace_json",
        type=Path,
        help="Path to the input trace JSON file.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output HTML file path (default: input path with .html extension).",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the rendered HTML in the default browser.",
    )
    return parser.parse_args()


def build_html_document(trace_html: str, title: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{
      margin: 0;
      padding: 24px;
      background: #f8fafc;
      color: #0f172a;
    }}
  </style>
</head>
<body>
{trace_html}
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    trace_path = args.trace_json.expanduser().resolve()

    if not trace_path.exists():
        raise FileNotFoundError(f"Trace file not found: {trace_path}")

    trace = Trace.from_path(trace_path)
    trace_html = trace.visualize()

    output_path = args.output.expanduser().resolve() if args.output else trace_path.with_suffix(".html")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        build_html_document(trace_html, title=f"Trace View - {trace_path.name}"),
        encoding="utf-8",
    )

    print(f"Rendered trace HTML: {output_path}")
    if args.open:
        webbrowser.open(output_path.as_uri())


if __name__ == "__main__":
    main()
