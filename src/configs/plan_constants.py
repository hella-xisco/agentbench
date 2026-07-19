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

# Curated K1/K2 conditions — content lives in one manifest (M1-C output), the
# `condition` key is the only thing that differs between these configs.
_CURATED_MANIFEST_PATH = "context/global/data/m1c/curated_manifest.json"

CURATED_K1A_CONFIG = {  # no file, docs stripped separately via --remove_docs
    "planner_class": "curated_planner",
    "manifest_path": _CURATED_MANIFEST_PATH,
    "condition": "k1a",
    "storage_dir": "output/plans",
}
CURATED_K1B_CONFIG = deepcopy(CURATED_K1A_CONFIG)
CURATED_K1B_CONFIG["condition"] = "k1b"

CURATED_K1C_CONFIG = deepcopy(CURATED_K1A_CONFIG)
CURATED_K1C_CONFIG["condition"] = "k1c"

CURATED_K2A_CONFIG = deepcopy(CURATED_K1A_CONFIG)
CURATED_K2A_CONFIG["condition"] = "k2a"

CURATED_K2B_CONFIG = deepcopy(CURATED_K1A_CONFIG)
CURATED_K2B_CONFIG["condition"] = "k2b"

ALL_PLAN_CONFIGS = {
    "baseline": BASELINE_PLAN_CONFIG,
    "oracle": ORACLE_CONFIG,
    "no_plan": NO_PLAN,
    "human_planner": HUMAN_PLANNER,
    "codex_planner": CODEX_PLAN_CONFIG,
    "claude_planner": CLAUDE_PLAN_CONFIG,
    "qwen_planner": QWEN_PLAN_CONFIG,
    "gemini_planner": GEMINI_PLAN_CONFIG,
    "curated_k1a": CURATED_K1A_CONFIG,
    "curated_k1b": CURATED_K1B_CONFIG,
    "curated_k1c": CURATED_K1C_CONFIG,
    "curated_k2a": CURATED_K2A_CONFIG,
    "curated_k2b": CURATED_K2B_CONFIG,
}


def is_plan_training_sequential(plan_type: str) -> bool:
    return plan_type in {}