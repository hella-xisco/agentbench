# Benchmark Generator

This module builds AgentBench-style instances from real GitHub pull requests, then publishes them as a Hugging Face dataset.

The current implementation follows the same high-level construction idea described in `main.pdf` (AGENTBENCH generation): mine PRs, filter for suitable tasks, prepare runnable setup/tests, generate standardized task statements and tests, then keep only validated instances.

## What the pipeline does

The main entrypoint is `scripts/benchmark_gen_scripts/run.sh`, which runs:

1. Config/bootstrap:
- Looks up repo config in `src/benchmark_generator/config.py`.
- If missing, builds a Docker image and inserts a new config entry via `build_repo_image.py`.
2. Instance generation:
- Runs `run_pipeline.py`, which executes these stages:
  - `triage`: keep PRs likely to yield deterministic, testable tasks.
  - `setup`: infer setup/test commands needed to run the repository.
  - `statement`: produce a standardized task description.
  - `instance`: generate instance tests/patch artifacts.
  - `filtering`: keep only instances that fail before patch and pass after patch.
3. Dataset publish:
- Runs `finalize_repo.py` to push filtered instances to Hugging Face Hub.

## Prerequisites

- Docker available locally (instances are executed in Docker images).
- Python project dependencies installed for this repository.
- Model/provider credentials configured for your selected model/generator configs.
- `GITHUB_TOKEN` recommended for PR fetching (otherwise GitHub rate limits may apply).
- Hugging Face authentication configured for `push_to_hub` (for `finalize_repo.py`).

## Quick start

```bash
REPO=opshin/opshin \
REPO_REF=main \
DATASET_NAME=eth-sri/agentbench \
OUTPUT=benchmark_generation/test_setup \
bash scripts/benchmark_gen_scripts/run.sh
```

Notes:

- `DATASET_NAME` is used when `run.sh` has to create a new repo config entry.
- If the repo already exists in `config.py`, its existing `dataset_name` and `docker_image` are reused.

## Environment variables (`run.sh`)

Repository/output:

- `REPO` (default: `opshin/opshin`)
- `REPO_REF` (default: `main`)
- `OUTPUT` (default: `benchmark_generation/test_setup`)
- `DATASET_NAME` (default: `eth-sri/agentbench`)

Models/generators:

- `TRIAGE_MODEL`, `TRIAGE_GENERATOR`
- `STATEMENT_MODEL`, `STATEMENT_GENERATOR`
- `INSTANCE_MODEL`, `INSTANCE_GENERATOR`
- `FILTER_MODEL`, `FILTER_GENERATOR`

Defaults for all model vars: `gpt-5-codex`  
Defaults for all generator vars: `codex`

Parallelism and limits:

- `TRIAGE_WORKERS=8`
- `SETUP_WORKERS=$TRIAGE_WORKERS`
- `STATEMENT_WORKERS=8`
- `INSTANCE_WORKERS=8`
- `FILTER_WORKERS=8`
- `LIMIT=-1` (all cached PRs)
- `TARGET_INSTANCES=10` (stop once enough accepted instances exist)
- `PARALLEL_INSTANCES=8` (how many PR pipelines run concurrently)

## Output structure

For `REPO=owner/name`, outputs go under `OUTPUT/owner_name/`:

- `pr_cache/`: cached PR metadata and patches
- `triage_results/`: PRs accepted by triage
- `setup_results/`: PRs with inferred setup/test commands
- `statements/`: PRs with generated standardized statements
- `generated_instances/`: generated instance artifacts
- `filtered_instances/`: validated final instances (used for publish)

`run_pipeline.py` also serves a live status page by default at `http://127.0.0.1:8000`.

## Final dataset columns and downstream usage

Each row pushed by `finalize_repo.py` contains the following columns (+metadata) that are used by the AGENTbench harness:

- `instance_id`: lookup key for filtering, evaluation selection, reports.
- `base_repo`: repository slug to evaluate.
- `problem_description`: task prompt shown to the coding agent.
- `clean_pr_patch`: reference patch (used for oracle / `use_pr_patch` evaluation).
- `docker_image`: execution image for Docker environment.
- `base_sha`: commit checked out before setup and patch application.
- `setup_commands`: repository setup commands.
- `repo_test_commands`: commands that run repo-wide regression tests.
- `repo_test_runner`: script content written as `run_tests.py`.
- `test_file_names`: per-instance test file paths.
- `test_file_contents`: per-instance test file bodies.
- `test_file_runner`: script content written as `run_pr_tests.py`.
- `test_commands`: commands that execute per-instance tests.
- `repo_test_after_pr_patch`: baseline repo-test outcomes after PR patch; used to ensure model patches do not regress tests that should remain passing.

## Common direct commands

Build/register config and image manually:

```bash
python3 scripts/benchmark_gen_scripts/build_repo_image.py \
  owner/name \
  --ref main \
  --dataset-name org/dataset
```

Run generation only (no publish):

```bash
python3 scripts/benchmark_gen_scripts/run_pipeline.py \
  --repo owner/name \
  --output benchmark_generation/test_setup \
  --target_instances 10
```

Publish already-filtered instances:

```bash
python3 scripts/benchmark_gen_scripts/finalize_repo.py \
  --repo owner/name \
  --output benchmark_generation/test_setup
```
