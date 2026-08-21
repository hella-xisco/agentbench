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

# Curated conditions (final cell set 20.08.: K0d/K1/K1s/K2/K2s) — content lives
# in one manifest (M1-C output), the `condition` key is the only thing that
# differs between these configs. K0 runs via no_plan, not via this manifest.
_CURATED_MANIFEST_PATH = "data/m1c/curated_manifest.json"

CURATED_K0D_CONFIG = {  # original DEV file verbatim as AGENTS.md
    "planner_class": "curated_planner",
    "manifest_path": _CURATED_MANIFEST_PATH,
    "condition": "k0d",
    "storage_dir": "output/plans",
}
CURATED_K1_CONFIG = deepcopy(CURATED_K0D_CONFIG)   # procedural, AGENTS.md
CURATED_K1_CONFIG["condition"] = "k1"

CURATED_K1S_CONFIG = deepcopy(CURATED_K0D_CONFIG)  # procedural, SKILL.md
CURATED_K1S_CONFIG["condition"] = "k1s"

CURATED_K2_CONFIG = deepcopy(CURATED_K0D_CONFIG)   # descriptive, AGENTS.md
CURATED_K2_CONFIG["condition"] = "k2"

CURATED_K2S_CONFIG = deepcopy(CURATED_K0D_CONFIG)  # descriptive, SKILL.md
CURATED_K2S_CONFIG["condition"] = "k2s"

ALL_PLAN_CONFIGS = {
    "baseline": BASELINE_PLAN_CONFIG,
    "oracle": ORACLE_CONFIG,
    "no_plan": NO_PLAN,
    "human_planner": HUMAN_PLANNER,
    "codex_planner": CODEX_PLAN_CONFIG,
    "claude_planner": CLAUDE_PLAN_CONFIG,
    "qwen_planner": QWEN_PLAN_CONFIG,
    "gemini_planner": GEMINI_PLAN_CONFIG,
    "curated_k0d": CURATED_K0D_CONFIG,
    "curated_k1": CURATED_K1_CONFIG,
    "curated_k1s": CURATED_K1S_CONFIG,
    "curated_k2": CURATED_K2_CONFIG,
    "curated_k2s": CURATED_K2S_CONFIG,
}


def is_plan_training_sequential(plan_type: str) -> bool:
    return plan_type in {}