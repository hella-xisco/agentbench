# AGENTBench Harness

This repository contains the harness used in our paper for evaluating coding agents with different repository-level context settings (`NONE`, `LLM`, `HUMAN`) on:

- AGENTBench datasets (for example `eth-sri/agentbench`)
- SWE-Bench Lite datasets (for example `SWE-bench/SWE-bench_Lite`)

The design follows the paper pipeline (Figure 1): generate context/instructions, run an autonomous coding agent, evaluate produced patches with tests, then analyze traces and costs.

## Quick Start

### 1) Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

You also need Docker available locally for benchmark execution.

### 2) Choose model access: API key or local vLLM

You must either export provider API keys or run local vLLM endpoints.

API-key path (examples):

```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export GEMINI_API_KEY=...
export OPENROUTER_API_KEY=...
```

Local vLLM path (Qwen + GPT-OSS):

```bash
cd scripts
bash local_lms/vllm_qwen.sh 0.0.0.0 4000
bash local_lms/vllm_gpt-oss.sh 0.0.0.0 4001
```

Model configs for local models live in `src/configs/model_constants.py` and already point to `http://localhost:4000/v1` and `http://localhost:4001/v1`.

## Harness Entry Scripts

The harness has three entrypoints under `scripts/agentbench/run_harness/`:

### `generate.py`

Runs planning + coding-agent generation over benchmark instances.

- Loads model/planner/generator/benchmark configs from `src/configs/`
- Creates benchmark instances (`AgentbenchBenchmark` or `SweBench`)
- For each instance: setup Docker env, run planner (writes `AGENTS.md`/`CLAUDE.md`), run coding agent, save trajectory + patch
- Writes predictions to `preds.json` in the computed run directory

Example:

```bash
python scripts/agentbench/run_harness/generate.py \
  --plan_type codex_planner \
  --exec_model gpt-5.2-codex \
  --generator codex \
  --plan_model gpt-5.2-codex \
  --plan_generator codex \
  --benchmark agentbench \
  --dataset_name eth-sri/agentbench \
  --output_dir output/agentbench_v1_runs \
  --workers 8 \
  --run_id 0
```

### `evaluate.py`

Evaluates generated patches by running benchmark test logic.

- Reads `preds.json` from the generation output
- Dispatches to benchmark `solve(...)`
- For SWE-Bench, calls the official evaluation runner
- For AGENTBench, replays each instance with repo tests + instance tests
- Writes per-instance `report.json` files

Example:

```bash
python scripts/agentbench/run_harness/evaluate.py \
  --plan_type codex_planner \
  --exec_model gpt-5.2-codex \
  --generator codex \
  --plan_model gpt-5.2-codex \
  --plan_generator codex \
  --benchmark agentbench \
  --dataset_name eth-sri/agentbench \
  --output_dir output/agentbench_v1_runs \
  --workers 8 \
  --run_id 0
```

### `analyze.py`

Aggregates execution/evaluation artifacts into a CSV.

- Loads `report.json`, trajectories (`*.traj.json`), and optional cached plans
- Extracts metrics: resolved/pass-fail tests, cost, number of steps, tool calls, patch sizes, token stats
- Appends one row per instance to a CSV (default `results.csv`)

Example:

```bash
python scripts/agentbench/run_harness/analyze.py \
  --plan_type codex_planner \
  --exec_model gpt-5.2-codex \
  --generator codex \
  --plan_model gpt-5.2-codex \
  --plan_generator codex \
  --dataset_name eth-sri/agentbench \
  --output_dir output/agentbench_v1_runs \
  --csv experiment1_reasoning.csv \
  --run_id 0
```

## More Documentation

If you want a detailed architecture and internals guide for the harness implementation, read `src/agentbench/README.md`.

If you want to build or publish new AGENTBench-style datasets (PR mining, triage, setup, statement generation, test generation, filtering), start with `src/benchmark_generator/README.md`.

If you want to reproduce the paper experiments exactly, use the curated scripts in `final_scripts/` and read `final_scripts/README.md` for experiment-to-figure mapping.

## Acknowledgments

Some code from this repository was forked from the [mini-swe-agent repo](https://github.com/SWE-agent/mini-swe-agent/blob/main/LICENSE.md).
We thank the authors of mini-SWE-agent and we recommend checking their work!

## Citation

If you find our work useful, please cite out paper.
```
@misc{gloaguen2026evaluatingagentsmdrepositorylevelcontext,
      title={Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?}, 
      author={Thibaud Gloaguen and Niels Mündler and Mark Müller and Veselin Raychev and Martin Vechev},
      year={2026},
      eprint={2602.11988},
      archivePrefix={arXiv},
      primaryClass={cs.SE},
      url={https://arxiv.org/abs/2602.11988}, 
}
```
