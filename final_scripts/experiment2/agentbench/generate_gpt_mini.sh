#!/usr/bin/env bash

# COMMON SETTINGS
dataset_name=eth-sri/agentbench
benchmark="agentbench"
slice_spec="0:139"
output="output/agent_bench_traces"
train_plan=no
continuous_training=yes
workers=16
debug=False
PLAN_ARGS_TEMPLATES=("" "")
HISTORIES=("null" "null")
IDS=(0)
port=18140

# PARTICULAR SETTINGS
PLAN_TYPES=("codex_planner" "codex_planner")
PLAN_MODELS=("gpt-5.2-codex" "gpt-5.1-codex-mini")
PLAN_GENERATORS=("codex" "codex")
exec_model=gpt-5.1-codex-mini
generator=codex

# Guard: arrays must be the same length
if [[ ${#PLAN_TYPES[@]} -ne ${#PLAN_ARGS_TEMPLATES[@]} ]] || \
   [[ ${#PLAN_TYPES[@]} -ne ${#PLAN_MODELS[@]} ]] || \
   [[ ${#PLAN_TYPES[@]} -ne ${#PLAN_GENERATORS[@]} ]]; then
  echo "Error: plan arrays must all have the same length." >&2
  exit 1
fi

for ID in "${IDS[@]}"; do
    for ((i=0; i<${#PLAN_TYPES[@]}; i++)); do

        plan_type="${PLAN_TYPES[i]}"
        plan_model="${PLAN_MODELS[i]}"
        plan_generator="${PLAN_GENERATORS[i]}"
        plan_args_template="${PLAN_ARGS_TEMPLATES[i]}"
        HISTORY="${HISTORIES[i]}"

        python scripts/agentbench/run_harness/generate.py \
            --plan_type "$plan_type" \
            --exec_model "$exec_model" \
            --generator "$generator" \
            --slice_spec "$slice_spec" \
            --plan_args "${plan_args_template}${HISTORY}" \
            --dataset_name "$dataset_name" \
            --run_id "$ID" \
            --port "$port" \
            --output_dir "$output" \
            --train_plan "$train_plan" \
            --continuous_training "$continuous_training" \
            --benchmark "$benchmark" \
            --workers "$workers" \
            --plan_model "$plan_model" \
            --plan_generator "$plan_generator" \
            --debug "$debug"
    done
done
