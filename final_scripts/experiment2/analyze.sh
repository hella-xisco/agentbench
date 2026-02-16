#!/usr/bin/env bash

# COMMON SETTINGS
dataset_name=eth-sri/agentbench
benchmark="agentbench"
output="output/agentbench_v1_runs"
csv_file="experiment2.csv"
PLAN_ARGS_TEMPLATES=("")
HISTORIES=("null")
IDS=(0) 

# PARTICULAR SETTINGS
PLAN_TYPES_GLOBAL=("codex_planner" "codex_planner" "codex_planner" "qwen_planner" "codex_planner" "claude_planner")
PLAN_MODELS=("gpt-5.2-codex" "gpt-5.2-codex" "gpt-5.2-codex" "qwen3-30b-coder" "gpt-5.1-codex-mini" "sonnet-4-5")
PLAN_GENERATORS=("codex" "codex" "codex" "qwen_code" "codex" "claude_code")
EXEC_MODELS=("qwen3-30b-coder" "gpt-5.1-codex-mini" "sonnet-4-5" "qwen3-30b-coder" "gpt-5.1-codex-mini" "sonnet-4-5")
GENERATORS=("qwen_code" "codex" "claude_code" "qwen_code" "codex" "claude_code")


for IDX in "${!PLAN_TYPES_GLOBAL[@]}"; do

    plan_type="${PLAN_TYPES_GLOBAL[IDX]}"
    exec_model="${EXEC_MODELS[IDX]}"
    generator="${GENERATORS[IDX]}"
    plan_model="${PLAN_MODELS[IDX]}"
    plan_generator="${PLAN_GENERATORS[IDX]}"

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




# COMMON SETTINGS
dataset_name=SWE-bench/SWE-bench_Lite
output="output/swebench_lite"


for IDX in "${!PLAN_TYPES_GLOBAL[@]}"; do

    plan_type="${PLAN_TYPES_GLOBAL[IDX]}"
    exec_model="${EXEC_MODELS[IDX]}"
    generator="${GENERATORS[IDX]}"
    plan_model="${PLAN_MODELS[IDX]}"
    plan_generator="${PLAN_GENERATORS[IDX]}"



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
output="output/agentbench_v1_runs"


# PARTICULAR SETTINGS
EXEC_MODELS=("sonnet-4-5" "qwen3-30b-coder" "gpt-5.1-codex-mini")
GENERATORS=("claude_code" "qwen_code" "codex")


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


# PARTICULAR SETTINGS
EXEC_MODELS=("sonnet-4-5" "qwen3-30b-coder" "gpt-5.1-codex-mini")
GENERATORS=("claude_code" "qwen_code" "codex")

# COMMON SETTINGS
dataset_name=SWE-bench/SWE-bench_Lite
output="output/swebench_lite"


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
