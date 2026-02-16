#!/usr/bin/env bash

# COMMON SETTINGS
dataset_name=eth-sri/agentbench
benchmark="agentbench"
output="output/agentbench_v1_runs_nodocs"
csv_file="experiment4.csv"
PLAN_ARGS_TEMPLATES=("")
HISTORIES=("null")
IDS=(0) 

# PARTICULAR SETTINGS
PLAN_TYPES_GLOBAL=("qwen_planner" "codex_planner" "codex_planner")
EXEC_MODELS=("qwen3-30b-coder" "gpt-5.2-codex" "gpt-5.1-codex-mini")
GENERATORS=("qwen_code" "codex" "codex")


for IDX in "${!PLAN_TYPES_GLOBAL[@]}"; do

    plan_type="${PLAN_TYPES_GLOBAL[IDX]}"
    exec_model="${EXEC_MODELS[IDX]}"
    generator="${GENERATORS[IDX]}"
    plan_model="${EXEC_MODELS[IDX]}"
    plan_generator="${GENERATORS[IDX]}"

    for ID in "${IDS[@]}"; do

        python scripts/agentbench/run_harness/analyze.py \
            --plan_type "$plan_type" \
            --exec_model "$exec_model" \
            --generator "$generator" \
            --dataset_name "$dataset_name" \
            --run_id "$ID" \
            --output_dir "$output" \
            --plan_model "$plan_model" \
            --plan_generator "$plan_generator" \
            --csv "$csv_file" 
    done
done

###############################################
# NO PLAN ANALYSIS
###############################################
# COMMON SETTINGS
dataset_name=eth-sri/agentbench
output="output/agentbench_v1_runs_nodocs"


# PARTICULAR SETTINGS
EXEC_MODELS=("qwen3-30b-coder" "gpt-5.2-codex" "gpt-5.1-codex-mini")
GENERATORS=("qwen_code" "codex" "codex")


for IDX in "${!EXEC_MODELS[@]}"; do

    PLAN_TYPES_GLOBAL=("human_planner" "no_plan")

    exec_model="${EXEC_MODELS[IDX]}"
    generator="${GENERATORS[IDX]}"
    plan_model="${EXEC_MODELS[IDX]}"
    plan_generator="${GENERATORS[IDX]}"

    for plan_type in "${PLAN_TYPES_GLOBAL[@]}"; do

        for ID in "${IDS[@]}"; do

            python scripts/agentbench/run_harness/analyze.py \
                --plan_type "$plan_type" \
                --exec_model "$exec_model" \
                --generator "$generator" \
                --dataset_name "$dataset_name" \
                --run_id "$ID" \
                --output_dir "$output" \
                --plan_model "$plan_model" \
                --plan_generator "$plan_generator" \
                --csv "$csv_file" 
        done
    done
done