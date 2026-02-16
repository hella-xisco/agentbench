# AGENTBench Harness Internals

This document explains how the harness in `src/agentbench/` is structured, why key design choices were made, and where to modify behavior safely.

The harness is built around five abstractions:

- `Benchmark`: loads and evaluates task instances.
- `Instance`: owns setup + per-task execution/evaluation logic.
- `Planner`: prepares repository context files (`AGENTS.md` / `CLAUDE.md`).
- `Generator`: runs a coding agent and returns a patch.
- `Model`: provides model access and cost/tracing metadata.

See the protocol definitions in `src/agentbench/__init__.py`.

## End-to-End Flow

High-level runtime flow (from `scripts/agentbench/run_harness/generate.py`):

1. Load configs from `src/configs/`.
2. Build benchmark and fetch `instances`.
3. Start a LiteLLM proxy once for the execution model port.
4. For each instance:
   - create environment (Docker)
   - run planner (write context file)
   - run generator (wrapped coding CLI)
   - save trajectory and append prediction in `preds.json`
5. Stop model server.

Then:

- `evaluate.py` loads predictions and calls benchmark `solve(...)`.
- `analyze.py` joins reports + trajectories + plans into CSV metrics.

Important runtime details:

- generation runs instances in parallel threads (`ThreadPoolExecutor`)
- each worker constructs its own `Model`/`Planner`/`Generator` objects
- `preds.json` is updated with a file lock to avoid races
- trajectories are saved per instance even on failure paths

## Module Layout

- `benchmarks/`: benchmark adapters (`agentbench.py`, `swebench.py`)
- `environments/`: execution backends (`docker.py`)
- `generators/`: coding-agent wrappers (`cli_agent.py`, `miniswe_agents.py`)
- `model/`: model wrappers and LiteLLM proxy integration
- `planners/`: context-file generation/fetch strategies
- `utils/`: diffs, trajectory save/load, trace parsing, logging helpers

## Model + LiteLLM Design

A key implementation detail is the `LitellmServer` wrapper in `src/agentbench/model/litellm_wrapper/litellm_server.py`.

### Serving lifecycle

Before any `query(...)`, a proxy must be running. Call:

```python
model = get_model(config)
model.serve()
```

You only need to call `.serve()` once per `(host, port)` server. If you create multiple model objects that point to the same proxy port, do not start duplicate servers on the same port.

In this codebase, `generate.py` starts one server before worker execution. Instance-level model objects then use that same proxy endpoint for requests and trace accounting.

This is intentional: one process-level server, many instance-level model objects.

### Multi-instance model behavior in `generate.py`

`generate.py` uses two model-object roles:

- server owner: one model object in the main thread calls `.serve()` and holds the proxy process lifecycle
- instance trackers: each worker creates a model object with the same port, but it is mainly used to provide connection args and isolate trace/cost bookkeeping

Because all of them point to the same proxy URL but have different API keys, they can run concurrently while still producing separable traces.

### Why per-model API keys exist

Each `LitellmServer` object generates a random API key (`self._api_key`). That key is passed to coding-agent CLIs via environment variables (through `Generator` launch commands). LiteLLM callback logging (`litellm_logger.py`) extracts `user_api_key` metadata and writes traces to:

- `logs/litellm_server/traces/<api_key>.json`

This gives per-model-object request separation, even when several runs share one proxy endpoint.

Practical effect:

- cost and call counts can be computed per object from its own trace file
- trajectory saving can attach per-instance model stats reliably
- retries can delete only that object’s trace file without touching others

### Cost computation

`LitellmServer.get_cost()`:

- reads success events from its trace file
- aggregates token usage by response model
- prices usage using `MODEL_PRICES` logic from `src/agentbench/utils/trace.py`

The harness uses this for live dashboards and final metrics.

### Retry and failure behavior

The generation loop retries `APIError` up to `MAX_RETRIES` (10 in `generate.py`). On each retry it clears the current instance trace file via `model.delete_traces()` to avoid mixing partial/failed calls with the next attempt.

## Planner Design (Context Files)

Planners are responsible for repository-level context before coding starts.

Key behaviors:

- planner writes `AGENTS.md` (and often `CLAUDE.md`) into repo root
- planner may cache extracted plans in `extracted_plans.json`
- storage path is derived from planner config and dataset/model settings

Implemented planners:

- `no_plan`: remove existing agent docs, write nothing
- `human_planner`: fetches existing historical `AGENTS.md`/`CLAUDE.md` from git history
- `baseline` / `init_planner`: generate context file with a coding agent prompt
- `oracle`: generates guidance using ground-truth patch (analysis mode)

Plan extraction is handled by `src/agentbench/planners/utils/plan_extractor.py`.

Plan-model behavior:

- if `plan_model == exec_model`, planning uses the main model/proxy path
- if `plan_model != exec_model`, `generate.py` starts a second model server on `port + 1` and passes its config into planner `model_config`

## Generator Design (CLI Wrapping)

`src/agentbench/generators/cli_agent.py` unifies Codex/Claude/Qwen/Gemini CLIs behind one interface.

Generator responsibilities:

- run install commands and post-install setup
- inject model connection args (`api_key`, `base_url`, `model`) into launch command
- execute CLI in benchmark environment
- parse LiteLLM traces into message history
- produce final patch via `git diff --cached`

Design choice: the harness treats each external CLI as a black-box executor but normalizes output into a single trajectory format (`save_traj` in `src/agentbench/utils/io_utils.py`).

## Benchmark + Instance Design

`Benchmark` classes load datasets and expose filtered `instances`. `Instance` classes own setup and evaluation specifics.

### AGENTBench benchmark

`src/agentbench/benchmarks/agentbench.py`:

- datasets include setup commands, test runners, and instance tests
- `Instance.setup(...)` checks out base commit and prepares environment
- `Instance.solve(...)` applies model patch and runs:
  - repo regression tests
  - instance-specific tests
- writes `report.json` per instance with resolved/pass metadata
- can optionally enforce repo-regression safety against `repo_test_after_pr_patch` baselines

### SWE-Bench benchmark

`src/agentbench/benchmarks/swebench.py`:

- adapts SWE-Bench dataset rows to harness `Instance` objects
- evaluation delegates to official SWE-Bench `run_evaluation(...)`
- writes SWE-Bench-style reports under run directory
- supports evaluating generated patches or directly evaluating ground-truth PR patches (`evaluate.py --use_pr_patch`)

## Environment Design

`src/agentbench/environments/docker.py` provides isolated execution in Docker.

Key choices:

- each instance runs in its own container
- commands are executed through `docker exec`
- environment supports command-length fallback via stdin
- network access is enabled (`--network=host`) to allow tool/web usage

For AGENTBench experiments, instance setup also removes remotes and rewrites git refs to avoid future-history leakage.

## Output and Run Directory Conventions

Directory naming is centralized in `src/agentbench/utils/io_utils.py::_compute_run_directory(...)`.

Typical artifacts:

- `preds.json`: generated patches keyed by `instance_id`
- `<instance>/<instance>.traj.json`: normalized conversation + responses
- `<instance>/report.json`: evaluation result for that instance
- planner cache files under configured `storage_dir`

This deterministic path scheme is why `evaluate.py` and `analyze.py` can infer where to load artifacts from using only run args.

Path convention note:

- generation outputs under `output/agentbench/...`
- evaluation reports under `output/swebench/...`
- analysis reads both trees to produce one tabular row per instance

## Trace and Analysis Layer

`src/agentbench/utils/trace.py` parses trajectories into:

- role components (system/user/assistant/tool)
- tool calls and outputs
- token usage and estimated cost
- first-read-file metrics and error-tool statistics

`scripts/agentbench/run_harness/analyze.py` uses this to build the paper-oriented CSV rows (steps, tool counts, first relevant read, reasoning tokens, patch-size metrics, etc.).

## Configuration Strategy

All configuration registries live in `src/configs/`:

- `model_constants.py`: model endpoints/kwargs and API-key env usage
- `generator_constants.py`: launch/install/post hooks for each coding CLI
- `plan_constants.py`: planner modes and defaults
- `benchmark_constants.py`: benchmark adapters and split defaults

Run scripts assemble these registries into a concrete runtime config object. This keeps experiment scripts simple and avoids hardcoded behavior in harness core modules.

## Extending The Harness

To add new functionality:

- New model backend:
  - implement `Model` protocol
  - register in `src/agentbench/model/__init__.py`
  - add config in `src/configs/model_constants.py`
- New coding agent wrapper:
  - implement `Generator`
  - register in `src/agentbench/generators/__init__.py`
  - add generator config in `src/configs/generator_constants.py`
- New planner mode:
  - implement `Planner`
  - register in `src/agentbench/planners/__init__.py`
  - add defaults in `src/configs/plan_constants.py`
- New benchmark:
  - implement `Benchmark` + `Instance`
  - register in `src/agentbench/benchmarks/__init__.py`
  - add benchmark config in `src/configs/benchmark_constants.py`

## Common Pitfalls

- Starting multiple LiteLLM proxies on the same port. Serve once per port.
- Forgetting `.serve()` before direct `query(...)` calls.
- Misaligning generator launch env variables with model `get_openai_args()`.
- Breaking run-directory conventions, which then breaks `evaluate.py`/`analyze.py` artifact lookup.
