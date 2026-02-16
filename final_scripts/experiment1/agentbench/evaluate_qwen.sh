#!/usr/bin/env bash

# COMMON SETTINGS
dataset_name=eth-sri/agentbench
benchmark="agentbench"
output="output/agentbench_v1_runs"
workers=32
PLAN_ARGS_TEMPLATES=("" "" "")
HISTORIES=("null" "null" "null")
IDS=(0) 

# PARTICULAR SETTINGS
PLAN_TYPES=("qwen_planner" "human_planner" "no_plan")
exec_model=qwen3-30b-coder
generator=qwen_code
plan_model=qwen3-30b-coder
plan_generator=qwen_code

# Guard: arrays must be the same length
if [[ ${#PLAN_TYPES[@]} -ne ${#PLAN_ARGS_TEMPLATES[@]} ]]; then
  echo "Error: PLAN_TYPES and PLAN_ARGS_TEMPLATES must have the same length." >&2
  exit 1
fi


for ID in "${IDS[@]}"; do
    for ((i=0; i<${#PLAN_TYPES[@]}; i++)); do

        plan_type="${PLAN_TYPES[i]}"
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
