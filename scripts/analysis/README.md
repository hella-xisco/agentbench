# Thesis analysis audit

This directory contains the reproducible Phase-B analysis source and the reporting layer that turns its versioned outputs into thesis assets. It does not replace the historical scripts in `scripts/` and never rewrites thesis prose. Generated tables and figures remain separate, inspectable artefacts.

The accepted v3 main-run source uses mean effort per measurable attempt uniformly across all research questions. Historical v2 effort ratios are not inputs to the current effort assets. Reporting does not change research questions, contrasts or solve-rate tests.

## Submission inputs

In the accompanying benchmark repository, byte-identical task manifests are under `data/analysis/`; the four configurations refer to those portable paths. `data/analysis/measurement-inputs.tar.gz.part-*` are ordered parts of one archive containing only the exact trajectory JSONs and evaluation reports required by the four matrices, at their original relative paths. Each part is at most 80 MiB. No proxy logs, API environment files, virtual environments or historical thesis analysis scripts are included. The verifier checks each part, the combined SHA-256 and every allowlisted input against `checksums.json`. From the **benchmark repository root**:

```bash
python3 scripts/analysis/verify_inputs.py --extract
```

Recalculating stored runs needs neither a model server nor Docker. Accepted pilot/v3 outputs are included for verification. Write recalculations to a fresh directory and compare them with the accepted outputs before replacing any result. For standalone asset reproduction, use `--table-output-dir reproduction/tables --figure-output-dir reproduction/figures` instead of the thesis paths below. Copy `figures/palette.json` into the same relative path if working outside the submission repository.

The following commands are the **submission-root workflow** and reproduce all four matrices and all five reporting subcommands without overwriting accepted results:

```bash
python3 scripts/analysis/verify_inputs.py --extract
uv sync --project scripts/analysis --frozen
uv run --project scripts/analysis python scripts/analysis/reproduce.py \
  --output-dir reproduction/new-run --render
```

`--render` requires `rsvg-convert` (librsvg); omit it to produce CSV, JSON, LaTeX tables and SVGs only. `--assets-only` uses the accepted pilot/main-run outputs, but still requires the extracted trajectories for behaviour assets. The output directory must not already exist. Run the tests with the command at the end of this README.

`data/analysis/thesis-assets.json` registers every numbered figure and table, with its label, caption, PDF appearance, source excerpt and file SHA-256. Companion source/rendered assets are under `data/analysis/thesis-assets/`. Conceptual TikZ/draw.io diagrams are supplied as source assets rather than represented as statistical outputs. To re-audit numbering and regenerate the register against the thesis source and compiled PDF, use:

```bash
python3 scripts/analysis/register_thesis_assets.py \
  --thesis-root /path/to/thesis --output /path/to/new-thesis-assets.json
```

## Environment

The individual command examples below refer to the thesis working repository. For the accompanying benchmark repository, use the submission-root workflow above; in particular, the reviewed statements there are at `categorized-data-set/coding/statements.csv`, without a leading `benchmark/` directory.

The project requires Python 3.12 or newer. NumPy 2.x and SciPy 1.x are pinned transitively by `uv.lock`.

```bash
uv sync --project scripts/analysis --frozen
uv run --project scripts/analysis thesis-variance-pilot \
  --config scripts/analysis/configs/vp_glm.json \
  --output-dir experiments/2026-08-20_01-vp-stufe1/analysis/variance-pilot-v2
uv run --project scripts/analysis thesis-main-run \
  --config scripts/analysis/configs/main_glm.json \
  --output-dir experiments/2026-08-21_01-hauptrun/analysis/statistics-v3
uv run --project scripts/analysis thesis-results-assets pilot-tables \
  --glm-pilot-output experiments/2026-08-20_01-vp-stufe1/analysis/variance-pilot-v2 \
  --qwen-pilot-output experiments/2026-08-22_02-vplight-qwen/analysis/variance-pilot-v2 \
  --glm-config scripts/analysis/configs/vp_glm.json \
  --output-dir chapters/tables
uv run --project scripts/analysis thesis-results-assets pilot-figures \
  --glm-pilot-output experiments/2026-08-20_01-vp-stufe1/analysis/variance-pilot-v2 \
  --qwen-pilot-output experiments/2026-08-22_02-vplight-qwen/analysis/variance-pilot-v2 \
  --palette figures/palette.json --output-dir figures --render
uv run --project scripts/analysis thesis-results-assets material-categorization \
  --statements benchmark/categorized-data-set/coding/statements.csv \
  --output-dir chapters/tables
uv run --project scripts/analysis thesis-results-assets main-overview \
  --glm-main-output experiments/2026-08-21_01-hauptrun/analysis/statistics-v3 \
  --qwen-main-output experiments/2026-08-25_01-hauptrun-qwen/analysis/statistics-v3 \
  --output-dir chapters/tables
uv run --project scripts/analysis thesis-results-assets main-results \
  --glm-main-output experiments/2026-08-21_01-hauptrun/analysis/statistics-v3 \
  --qwen-main-output experiments/2026-08-25_01-hauptrun-qwen/analysis/statistics-v3 \
  --palette figures/palette.json \
  --table-output-dir chapters/tables --figure-output-dir figures --render
```

Use `--audit-only` with `thesis-main-run` to stop after raw normalization, outcome counts, exclusions, and complete paired-set sample sizes. With the main-run repetition count of two, a complete paired set requires two measurable runs in each compared cell (the 2+2 rule).

## Versioned configurations

- `vp_glm.json`: GLM 10×20 pilot and the initial planning calculation.
- `vp_qwen.json`: Qwen 10×20 transfer check, including engine allocation and 81/200 timeouts.
- `main_glm.json`: GLM six-cell main run with two repetitions.
- `main_qwen.json`: Qwen six-cell main run with two repetitions.

Paths in configurations are resolved from the repository root. Only configured repetition directories are part of the matrix; historical smoke runs with other IDs are ignored. Within that matrix, every manifest task must have exactly one trajectory. Missing or additional task-run trajectories abort the analysis. A missing evaluation report remains visible as the non-measurable `missing_artifact` category.

## Statistical definitions

The pilot reports pass@1 for repetitions 1–10 and 1–20, solved-task counts per round, their sample standard deviation, each task's unbiased sample variance, and the unweighted mean of those variances. Design precision uses

`SE_plan = sqrt(2 * 0.1187 / (|T| * n))`

and the nominal two-sided t half-width `t_(0.975,N-1) * SE_plan`. Power, disagreement, and a noise-floor rule are deliberately absent from the pilot decision.

For every main-run contrast, a task is retained only if both repetitions in both cells are measurable. Task differences are `delta_t = p_hat_(a,t) - p_hat_(b,t)`. The CLI reports the mean difference, its sample standard deviation and standard error, a two-sided paired t test, and an individual t-based 95% interval. Holm adjustment is applied separately to the RQ1, RQ2, and RQ3 pass@1 families within each model.

The two main metrics are solve rate (pass@1) and **mean effort**. Mean effort is total resource expenditure divided by the number of measurable attempts, including failed attempts and timeouts. It is reported separately in tokens, model API calls and **run-time [s]**; there is no composite resource score or monetary-cost estimate. Run-time is the recorded elapsed run duration, not pure inference time. Technical input/output keys such as `wall_seconds` retain their original spelling.

For each contrast, both cells use exactly the same complete task set. Each cell mean divides its task-summed effort by `runs_per_task * n_tasks` (two runs per task in the main runs). The effort effect is mean a minus mean b. Tasks are resampled 10,000 times with seed 42, retaining both cells and all their repetitions. The same draws are used across all three units; intervals are the linear 2.5th and 97.5th percentiles of resampled mean differences. Zero solved runs remain valid and no draws are rejected on solved-count grounds. Missing, non-finite or negative effort measurements abort the analysis. No pass@1 bootstrap, effort significance test or effort Holm decision is produced.

A model API call is read from the harness metadata and remains distinct from tool calls used for trajectory analysis. Cell-level means use all measurable runs in that cell; they are not automatically the contrast-specific means. Task bootstrap intervals remain conditional on the observed task population and do not resolve repository dependence, selective missingness, or limited repetitions.

Pairwise disagreement is supplementary and uses only tasks with two measurable repetitions in a cell. The sole sensitivity analysis is `delivered-only` for the procedural contrasts; it excludes task prefixes listed in the configuration and reports only the task-set size, effect, and individual t interval.

## Outputs

Pilot directories contain `summary.json`, `task_estimates.csv`, `round_counts.csv`, `design_precision.csv`, `outcome_taxonomy.csv`, and `raw_status_mapping.csv`.

Main-run v3 directories contain `outcome_taxonomy.csv`, `raw_status_mapping.csv`, `cell_summaries.csv`, `contrast_sample_sizes.csv`, `contrast_exclusions.csv`, `contrast_results.csv`, `contrast_results.json`, `effort_results.csv`, `effort_bootstrap.json`, `pairwise_disagreement.csv`, `delivered_only_sensitivity.csv`, and `report.md`. The report records results but deliberately makes no RQ or thesis conclusion. Effort JSON explicitly declares `estimator: mean_effort_per_measurable_run`; each metric includes `mean_a`, `mean_b`, `effect`, `ci_low` and `ci_high`. CSV has one row per contrast and metric, with cell labels and task/run counts. The renderer rejects historical ratio JSONs for new mean-effort tables.

Existing `statistics-v2` results are historical and protected from overwriting. The source of the previous ratio pipeline is archived separately under `experiments/analysis-history/`. Historical scripts and the standalone `reviews/` diagnostics are not part of the final submission pipeline.

The reporting command reads only these generated outputs and the trajectory paths referenced by their raw-status mappings. Its `material-categorization` subcommand produces `tab-context-categorization.tex` from the reviewed statement data. `pilot-tables` produces `tab-pilot-summary-v2.tex` and `tab-pilot-design-v2.tex`. `main-overview` produces `tab-main-overview-v2.tex`, containing absolute outcome counts, and `tab-main-contrast-sets-v2.tex`. These legacy asset filenames do not identify the current main-run analysis version; their source comments do. `main-results` produces the RQ-specific pass@1 and mean-effort tables, recurrence and delivered-only tables, activation and behaviour tables, the loop audit and main-run figures. The pass@1 forest shows direction, magnitude and individual t uncertainty; the recurrence table supplies exact values and Holm decisions. The **mean-effort forest** has three independent resource scales and all seven contrasts grouped by RQ; GLM circles and Qwen diamonds use the same configuration colours as the pass@1 plot. It uses unrounded v3 differences and individual bootstrap endpoints, not historical ratios or significance labels. Pairwise disagreement instead describes repetitions within cells. Source paths and commands are embedded as comments or SVG metadata. Figure commands write SVG; `--render` additionally creates PDF and PNG using `rsvg-convert`.

## Tests

```bash
uv run --project scripts/analysis python -m unittest discover \
  -s scripts/analysis/tests -v
```
