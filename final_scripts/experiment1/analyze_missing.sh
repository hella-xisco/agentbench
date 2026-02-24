#!/usr/bin/env bash

# COMMON SETTINGS
dataset_name=eth-sri/agentbench
benchmark="agentbench"
output="output/agent_bench_traces"
csv_file="experiment1.csv"
PLAN_ARGS_TEMPLATES=("")
HISTORIES=("null")
IDS=(0) 

# PARTICULAR SETTINGS
PLAN_TYPES_GLOBAL=("claude_planner" "qwen_planner" "codex_planner" "codex_planner")
EXEC_MODELS=("sonnet-4-5" "qwen3-30b-coder" "gpt-5.2-codex" "gpt-5.1-codex-mini")
GENERATORS=("claude_code" "qwen_code" "codex" "codex")


###############################################
# NO PLAN ANALYSIS
###############################################


# PARTICULAR SETTINGS
EXEC_MODELS=("sonnet-4-5" "qwen3-30b-coder" "gpt-5.2-codex" "gpt-5.1-codex-mini")
GENERATORS=("claude_code" "qwen_code" "codex" "codex")

# COMMON SETTINGS
dataset_name=SWE-bench/SWE-bench_Lite
output="output/agent_bench_test_results"


for IDX in "${!EXEC_MODELS[@]}"; do

    plan_type="no_plan"
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
