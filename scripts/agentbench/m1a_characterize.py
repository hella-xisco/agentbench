#!/usr/bin/env python3
"""M1-A Dataset Characterization — K1/K2/K3 signal analysis.

K1: test file density per instance (from dataset)
K2: type annotation density (from clean_pr_patch as proxy)
K3: lint config presence per repo (GitHub API)

Run: python m1a_characterize.py [--token GITHUB_TOKEN] [--out out.json]
"""

import argparse
import json
import re
import sys
import time
import urllib.request
import urllib.error
from base64 import b64decode
from collections import Counter, defaultdict
from pathlib import Path

# ─── CLI ─────────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser()
parser.add_argument("--token", default=None, help="GitHub personal access token")
parser.add_argument("--out", default="m1a_results.json")
args = parser.parse_args()

GITHUB_TOKEN = args.token
OUT_PATH = Path(args.out)

# ─── GitHub API helper ────────────────────────────────────────────────────────

_call_count = 0

def gh_get(path: str, ref: str | None = None) -> dict | list | None:
    """GET https://api.github.com/<path>[?ref=<ref>]. Returns None on 404."""
    global _call_count
    url = f"https://api.github.com/{path}"
    if ref:
        url += f"?ref={ref}"
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            _call_count += 1
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        if e.code == 403:
            print(f"  [rate-limit] sleeping 60s after {_call_count} calls...", file=sys.stderr)
            time.sleep(60)
            return gh_get(path, ref)
        raise


def gh_file_content(owner_repo: str, filepath: str, sha: str) -> str | None:
    """Fetch decoded text content of a single file at sha. None = not found."""
    data = gh_get(f"repos/{owner_repo}/contents/{filepath}", ref=sha)
    if data is None:
        return None
    if isinstance(data, list):  # directory
        return None
    raw = data.get("content", "")
    try:
        return b64decode(raw).decode("utf-8", errors="replace")
    except Exception:
        return None


# ─── Load dataset ─────────────────────────────────────────────────────────────

print("Loading dataset eth-sri/agentbench ...", file=sys.stderr)
from datasets import load_dataset  # noqa: E402
ds = load_dataset("eth-sri/agentbench", split="train")
print(f"  {len(ds)} instances loaded.", file=sys.stderr)

# Build per-repo structure
# Use most-recent base_sha as representative sha per repo
repo_data: dict[str, dict] = {}  # base_repo → {base_repo, instances: [...]}
for row in ds:
    r = row["base_repo"]
    if r not in repo_data:
        repo_data[r] = {"base_repo": r, "instances": []}
    repo_data[r]["instances"].append(row)

# Pick representative sha: latest merged_at
for r, d in repo_data.items():
    insts = d["instances"]
    insts.sort(key=lambda x: x.get("merged_at") or "")
    d["repr_sha"] = insts[-1]["base_sha"]


# ─── K1: Test file density ────────────────────────────────────────────────────
# From dataset field test_file_names (list of paths inside repo)

print("\n=== K1: Test file density ===", file=sys.stderr)

k1_per_repo = {}
for r, d in repo_data.items():
    instances = d["instances"]
    counts = [len(inst["test_file_names"]) for inst in instances]
    k1_per_repo[r] = {
        "n_instances": len(instances),
        "min_test_files": min(counts),
        "max_test_files": max(counts),
        "mean_test_files": round(sum(counts) / len(counts), 2),
        "instances_with_zero_tests": sum(1 for c in counts if c == 0),
    }

# Global summary
all_counts = [len(inst["test_file_names"]) for inst in ds]
k1_global = {
    "total_instances": len(ds),
    "instances_with_tests": sum(1 for c in all_counts if c > 0),
    "instances_without_tests": sum(1 for c in all_counts if c == 0),
    "mean_test_files": round(sum(all_counts) / len(all_counts), 2),
    "viable": sum(1 for c in all_counts if c == 0) == 0,
}

print(f"  Instances with tests: {k1_global['instances_with_tests']}/{k1_global['total_instances']}", file=sys.stderr)
print(f"  K1 viable: {k1_global['viable']}", file=sys.stderr)


# ─── K2: Type annotation density (clean_pr_patch proxy) ──────────────────────
# Proxy: scan Python files changed in clean_pr_patch for type annotations.
# Not whole-repo, but represents agent-relevant files.

print("\n=== K2: Type annotation density (patch proxy) ===", file=sys.stderr)

_ANN_PATTERN = re.compile(
    r"def\s+\w+\s*\(.*?(?::\s*\w[\w\.\[\], ]*)?.*?\)\s*(?:->\s*\S+)?\s*:",
)
_TYPED_FN = re.compile(
    r"def\s+\w+\s*\(.*?(?:[a-zA-Z_]\w*\s*:\s*[a-zA-Z_]|\)\s*->)",
)
_ANY_FN = re.compile(r"^\s*def\s+", re.MULTILINE)

def annotation_density(python_src: str) -> float:
    """Fraction of function defs that have at least one type annotation."""
    total = len(_ANY_FN.findall(python_src))
    if total == 0:
        return 0.0
    typed = len(_TYPED_FN.findall(python_src))
    return round(typed / total, 3)

k2_per_repo: dict[str, dict] = {}
for r, d in repo_data.items():
    densities = []
    for inst in d["instances"]:
        patch = inst.get("clean_pr_patch") or ""
        # Extract Python source blocks from unified diff (added lines, + prefix)
        py_blocks = []
        current_file_is_py = False
        for line in patch.splitlines():
            if line.startswith("--- ") or line.startswith("+++ "):
                current_file_is_py = line.endswith(".py")
            elif current_file_is_py and line.startswith("+") and not line.startswith("+++"):
                py_blocks.append(line[1:])
        src = "\n".join(py_blocks)
        if src.strip():
            densities.append(annotation_density(src))
    if densities:
        k2_per_repo[r] = {
            "n_instances": len(d["instances"]),
            "mean_annotation_density": round(sum(densities) / len(densities), 3),
            "max_annotation_density": max(densities),
            "min_annotation_density": min(densities),
            "instances_analyzed": len(densities),
        }
    else:
        k2_per_repo[r] = {"n_instances": len(d["instances"]), "mean_annotation_density": 0.0,
                           "instances_analyzed": 0}

k2_global_mean = round(
    sum(v["mean_annotation_density"] * v["n_instances"] for v in k2_per_repo.values())
    / sum(v["n_instances"] for v in k2_per_repo.values()),
    3,
)
k2_viable = k2_global_mean > 0.20  # arbitrary threshold: >20% annotated = meaningful condition

print(f"  Global mean annotation density: {k2_global_mean}", file=sys.stderr)
print(f"  K2 viable (>0.20): {k2_viable}", file=sys.stderr)


# ─── K3: Lint config presence ─────────────────────────────────────────────────

print("\n=== K3: Lint config presence (GitHub API) ===", file=sys.stderr)

LINT_FILES = [
    ".ruff.toml",
    "mypy.ini",
    ".mypy.ini",
    "setup.cfg",  # check for [mypy] section
]
PYPROJECT_SECTIONS = [r"\[tool\.mypy\]", r"\[tool\.ruff\]", r"\[tool\.flake8\]"]

k3_per_repo: dict[str, dict] = {}
for r, d in repo_data.items():
    sha = d["repr_sha"]
    has_lint = False
    lint_sources = []

    # Check pyproject.toml
    content = gh_file_content(r, "pyproject.toml", sha)
    if content:
        for pat in PYPROJECT_SECTIONS:
            if re.search(pat, content):
                has_lint = True
                section = pat.replace(r"\[", "").replace(r"\]", "").replace("\\.", ".")
                lint_sources.append(f"pyproject.toml {section}")

    # Check standalone files
    for fname in LINT_FILES:
        fc = gh_file_content(r, fname, sha)
        if fc is not None:
            if fname == "setup.cfg":
                if re.search(r"\[mypy\]", fc):
                    has_lint = True
                    lint_sources.append("setup.cfg [mypy]")
            else:
                has_lint = True
                lint_sources.append(fname)

    k3_per_repo[r] = {
        "has_lint_config": has_lint,
        "lint_sources": lint_sources,
        "repr_sha": sha,
    }
    mark = "✓" if has_lint else "✗"
    sources_str = ", ".join(lint_sources) if lint_sources else "none"
    print(f"  {mark} {r}: {sources_str}", file=sys.stderr)

repos_with_lint = sum(1 for v in k3_per_repo.values() if v["has_lint_config"])
k3_viable = repos_with_lint >= 6

print(f"  Repos with lint config: {repos_with_lint}/12", file=sys.stderr)
print(f"  K3 viable (>=6 repos): {k3_viable}", file=sys.stderr)
print(f"  Total GitHub API calls: {_call_count}", file=sys.stderr)


# ─── Per-instance summary ─────────────────────────────────────────────────────

instances_summary = []
for inst in ds:
    patch = inst.get("clean_pr_patch") or ""
    py_blocks = []
    current_file_is_py = False
    for line in patch.splitlines():
        if line.startswith("--- ") or line.startswith("+++ "):
            current_file_is_py = line.endswith(".py")
        elif current_file_is_py and line.startswith("+") and not line.startswith("+++"):
            py_blocks.append(line[1:])
    src = "\n".join(py_blocks)
    ann_d = annotation_density(src) if src.strip() else None

    instances_summary.append({
        "instance_id": inst["instance_id"],
        "repo": inst["base_repo"],
        "base_sha": inst["base_sha"],
        "k1_test_file_count": len(inst["test_file_names"]),
        "k1_has_tests": len(inst["test_file_names"]) > 0,
        "k2_annotation_density_patch": ann_d,
        "k3_repo_has_lint": k3_per_repo.get(inst["base_repo"], {}).get("has_lint_config", False),
    })


# ─── Final output ─────────────────────────────────────────────────────────────

result = {
    "meta": {
        "dataset": "eth-sri/agentbench",
        "split": "train",
        "n_instances": len(ds),
        "n_repos": len(repo_data),
        "github_api_calls": _call_count,
    },
    "k1": {
        "global": k1_global,
        "per_repo": k1_per_repo,
        "verdict": "GO" if k1_global["viable"] else "NO-GO",
        "note": "All instances have ≥1 test file" if k1_global["viable"]
                else f"{k1_global['instances_without_tests']} instances have 0 test files — consider filtering",
    },
    "k2": {
        "global_mean_density": k2_global_mean,
        "per_repo": k2_per_repo,
        "verdict": "GO" if k2_viable else "WEAK",
        "note": "patch-file proxy; not whole-repo scan. >0.20 = meaningful condition.",
        "threshold": 0.20,
    },
    "k3": {
        "repos_with_lint": repos_with_lint,
        "total_repos": 12,
        "per_repo": k3_per_repo,
        "verdict": "GO" if k3_viable else "NO-GO",
        "note": f"{repos_with_lint}/12 repos have a lint config",
    },
    "instances": instances_summary,
}

OUT_PATH.write_text(json.dumps(result, indent=2))
print(f"\nResults written to {OUT_PATH}", file=sys.stderr)

# ─── Human-readable summary ───────────────────────────────────────────────────

print("\n" + "="*60)
print("M1-A SUMMARY")
print("="*60)
print(f"\nDataset: {len(ds)} instances, {len(repo_data)} repos")
print(f"\nK1 (remove tests)      : {result['k1']['verdict']}")
print(f"  {result['k1']['note']}")
print(f"\nK2 (remove type annots): {result['k2']['verdict']}")
print(f"  Global annotation density: {k2_global_mean:.1%}")
print(f"\nK3 (remove lint config): {result['k3']['verdict']}")
print(f"  {result['k3']['note']}")
print(f"\nPer-repo K3 detail:")
for r, v in sorted(k3_per_repo.items()):
    mark = "✓" if v["has_lint_config"] else "✗"
    sources = ", ".join(v["lint_sources"]) if v["lint_sources"] else "—"
    print(f"  {mark} {r}: {sources}")
print()
