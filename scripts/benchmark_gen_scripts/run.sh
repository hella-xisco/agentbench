#!/usr/bin/env bash
set -euo pipefail

# Override any of the variables below to run against a different repository or
# adjust models/generators without editing the commands.
REPO="${REPO:-opshin/opshin}"
REPO_REF="${REPO_REF:-main}"
OUTPUT="${OUTPUT:-benchmark_generation/test_setup}"
REPO_SLUG="${REPO//\//_}"
DATASET_NAME="${DATASET_NAME:-eth-sri/agentbench}"

# Ensure repo config exists; build and register it if missing.
if ! python3 - "$REPO" <<'PY'
import sys

from benchmark_generator.config import maybe_get_repo_config

repo = sys.argv[1] if len(sys.argv) > 1 else ""
sys.exit(0 if maybe_get_repo_config(repo) is not None else 1)
PY
then
  echo "No config entry found for ${REPO}; building repo image and registering config."
  python3 scripts/benchmark_gen_scripts/build_repo_image.py \
    "${REPO}" \
    --ref "${REPO_REF}" \
    --dataset-name "${DATASET_NAME}"
fi

TRIAGE_MODEL="${TRIAGE_MODEL:-gpt-5-codex}"
TRIAGE_GENERATOR="${TRIAGE_GENERATOR:-codex}"
STATEMENT_MODEL="${STATEMENT_MODEL:-gpt-5-codex}"
STATEMENT_GENERATOR="${STATEMENT_GENERATOR:-codex}"
INSTANCE_MODEL="${INSTANCE_MODEL:-gpt-5-codex}"
INSTANCE_GENERATOR="${INSTANCE_GENERATOR:-codex}"
FILTER_MODEL="${FILTER_MODEL:-gpt-5-codex}"
FILTER_GENERATOR="${FILTER_GENERATOR:-codex}"

TRIAGE_WORKERS="${TRIAGE_WORKERS:-8}"
SETUP_WORKERS="${SETUP_WORKERS:-$TRIAGE_WORKERS}"
STATEMENT_WORKERS="${STATEMENT_WORKERS:-8}"
INSTANCE_WORKERS="${INSTANCE_WORKERS:-8}"
FILTER_WORKERS="${FILTER_WORKERS:-8}"
LIMIT="${LIMIT:--1}"
TARGET_INSTANCES="${TARGET_INSTANCES:-10}"
PARALLEL_INSTANCES="${PARALLEL_INSTANCES:-8}"

python3 scripts/benchmark_gen_scripts/run_pipeline.py \
  --repo "${REPO}" \
  --output "${OUTPUT}" \
  --triage_model "${TRIAGE_MODEL}" \
  --triage_generator "${TRIAGE_GENERATOR}" \
  --statement_model "${STATEMENT_MODEL}" \
  --statement_generator "${STATEMENT_GENERATOR}" \
  --instance_model "${INSTANCE_MODEL}" \
  --instance_generator "${INSTANCE_GENERATOR}" \
  --filter_model "${FILTER_MODEL}" \
  --filter_generator "${FILTER_GENERATOR}" \
  --triage_workers "${TRIAGE_WORKERS}" \
  --setup_workers "${SETUP_WORKERS}" \
  --statement_workers "${STATEMENT_WORKERS}" \
  --instance_workers "${INSTANCE_WORKERS}" \
  --filter_workers "${FILTER_WORKERS}" \
  --limit "${LIMIT}" \
  --target_instances "${TARGET_INSTANCES}" \
  --parallel_instances "${PARALLEL_INSTANCES}"

python3 scripts/benchmark_gen_scripts/finalize_repo.py \
  --repo "${REPO}" \
  --output "${OUTPUT}" 
