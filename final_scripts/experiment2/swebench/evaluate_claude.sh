#!/usr/bin/env bash

# COMMON SETTINGS
dataset_name=SWE-bench/SWE-bench_Lite
benchmark="swebench"
output="output/agent_bench_test_results"
workers=32
PLAN_ARGS_TEMPLATES=("" "")
HISTORIES=("null" "null")
IDS=(0) 

# PARTICULAR SETTINGS
PLAN_TYPES=("codex_planner" "claude_planner")
PLAN_MODELS=("gpt-5.2-codex" "sonnet-4-5")
PLAN_GENERATORS=("codex" "claude_code")
exec_model=sonnet-4-5
generator=claude_code

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

        python scripts/agentbench/run_harness/evaluate.py \
            --plan_type "$plan_type" \
            --exec_model "$exec_model" \
            --generator "$generator" \
            --plan_args "${plan_args_template}${HISTORY}" \
            --dataset_name "$dataset_name" \
            --run_id "$ID" \
            --benchmark "$benchmark" \
            --output_dir "$output" \
            --workers "$workers" \
            --plan_model "$plan_model" \
            --plan_generator "$plan_generator"
    done
done
