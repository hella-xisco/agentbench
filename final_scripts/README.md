# Reproducing our results

This directory contains the scripts used to reproduce the experiments reported in
`main.pdf`. The folder structure follows the experiment numbering from the paper:
`experiment1`, `experiment2`, `experiment3`, and `experiment4`.

In each experiment folder, the general flow is:

1. Run `generate_*.sh` (or `run_*.sh`) to produce model patches.
2. Run `evaluate_*.sh` (or `run_*_eval.sh`) to execute tests and compute success.
3. Run `analyze.sh` to aggregate metrics into CSV outputs.

All scripts use the harness entrypoints in `scripts/agentbench/run_harness/`.

## Released Artifacts

The traces and test outputs are available [here](https://files.sri.inf.ethz.ch/agentbench/agentbench_traces.tar.zst).

From the repository root, download `agentbench_traces.tar.zst` and extract it with:

```bash
tar -xf agentbench_traces.tar.zst --use-compress-program='zstd -d'
```

This creates:

- `output/agent_bench_traces/`
- `output/agent_bench_test_results/`

The scripts in this folder are configured to use that layout.

## How experiments map to the paper

- `experiment1` reproduces the main evaluation:
  - Figure 3 (main performance: NONE vs LLM vs HUMAN)
  - Figure 4 (steps before first interaction with relevant files)
  - Figure 6 (tool-use deltas by concrete tool)
  - Figure 7 (reasoning token usage)
  - Figure 10 (appendix: tool-use deltas by high-level category)
  - Figure 11 (appendix: per-repository success rates)
  - Table 2 (steps and cost)
- `experiment2` reproduces:
  - Figure 8 ("Instruction by: Own vs GPT-5.2")
- `experiment3` reproduces:
  - Figure 9 ("Prompt from: Codex vs Claude Code")
- `experiment4` reproduces:
  - Figure 5 (no-documentation ablation on AGENTBENCH)

## Scope notes

- `experiment1` and `experiment2` include both AGENTBENCH and SWE-Bench Lite.
- `experiment4` is AGENTBENCH-only (the no-docs ablation).
- Figure 1, Figure 2, and Table 1 come from benchmark construction/statistics and
  are not produced by these run scripts.
