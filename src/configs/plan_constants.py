from copy import deepcopy


PLACEHOLDER = ""

BASELINE_PLAN_CONFIG = {
    "planner_class": "baseline_planner",
    "prompt_type": "codex_init",
    "storage_dir": "output/plans",
}

ORACLE_CONFIG = deepcopy(BASELINE_PLAN_CONFIG)
ORACLE_CONFIG["planner_class"] = "oracle_planner"
ORACLE_CONFIG.pop("prompt_type")

CODEX_PLAN_CONFIG = deepcopy(BASELINE_PLAN_CONFIG)
CODEX_PLAN_CONFIG["planner_class"] = "init_planner"
CODEX_PLAN_CONFIG["prompt_type"] = "codex_agentsmd"

CLAUDE_PLAN_CONFIG = deepcopy(CODEX_PLAN_CONFIG)
CLAUDE_PLAN_CONFIG["prompt_type"] = "claude_agentsmd"

QWEN_PLAN_CONFIG = deepcopy(CODEX_PLAN_CONFIG)
QWEN_PLAN_CONFIG["prompt_type"] = "qwen_agentsmd"

GEMINI_PLAN_CONFIG = deepcopy(CODEX_PLAN_CONFIG)
GEMINI_PLAN_CONFIG["prompt_type"] = "gemini_agentsmd"


NO_PLAN = {
    "planner_class": "no_plan",
    "storage_dir": "output/plans", # Dummy, not used
}

HUMAN_PLANNER = {
    "planner_class": "human_planner",
    "storage_dir": "output/plans",
}

ALL_PLAN_CONFIGS = {
    "baseline": BASELINE_PLAN_CONFIG,
    "oracle": ORACLE_CONFIG,
    "no_plan": NO_PLAN,
    "human_planner": HUMAN_PLANNER,
    "codex_planner": CODEX_PLAN_CONFIG,
    "claude_planner": CLAUDE_PLAN_CONFIG,
    "qwen_planner": QWEN_PLAN_CONFIG,
    "gemini_planner": GEMINI_PLAN_CONFIG,
}


def is_plan_training_sequential(plan_type: str) -> bool:
    return plan_type in {}