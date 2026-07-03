import os
from copy import deepcopy

##### API KEYS #####

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


#### Costs

# input, output, cache, cache_creation
MODEL_PRICES = {
    "Qwen3-Coder-30B-A3B-Instruct-FP8": (0.1, 0.3, 0.0, 0.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0, 0.10, 1.25),
    "claude-sonnet-4-5-20250929": (3.0, 15.0, 0.3, 3.75),
    "gpt-5-codex": (1.25, 10.0, 0.125, 0.0),
    "gpt-5.1-codex-mini": (0.25, 2.0, 0.025, 0.0),
    "gpt-5-mini-2025-08-07": (0.25, 2.0, 0.02, 0.0),
    "gpt-5.2-codex": (1.75, 14.0, 0.175, 0.0),
    "gemini-3-flash-preview": (0.25, 1.5, 0.05, 0.0),
}


###################### MODELS CONFIGURATION ######################

##########
# GEMINI #
##########

MODEL_GEMINI_FLASH = {
    "model_name": "gemini/gemini-3-flash-preview",
    "model_kwargs": {
        "temperature": 1.0,
        "api_key": GEMINI_API_KEY,
        "reasoning_effort": "high",
    },
}

#############
# ANTHROPIC #
#############

MODEL_OPUS = {
    "model_name": "anthropic/claude-opus-4-5-20251101",
    "model_kwargs": {
        "drop_params": True,
        "temperature": 0.0,
        "api_key": ANTHROPIC_API_KEY,
    },
}

MODEL_SONNET = {
    "model_name": "anthropic/claude-sonnet-4-5-20250929",
    "model_kwargs": {
        "drop_params": True,
        "temperature": 0.0,
        "api_key": ANTHROPIC_API_KEY,
    },
}

##########
# OPENAI #
##########

MODEL_GPT_5_MINI_HIGH = {
    "model_name": "openai/gpt-5-mini-2025-08-07",
    "model_kwargs": {
        "drop_params": True,
        "api_key": OPENAI_API_KEY,
        "reasoning_effort": "high",
    },
}
MODEL_GPT_5_MINI_MEDIUM = deepcopy(MODEL_GPT_5_MINI_HIGH)
MODEL_GPT_5_MINI_MEDIUM["model_kwargs"]["reasoning_effort"] = "medium"
MODEL_GPT_5_NANO_HIGH = deepcopy(MODEL_GPT_5_MINI_HIGH)
MODEL_GPT_5_NANO_HIGH["model_name"] = "openrouter/openai/gpt-5-nano-2025-08-07"
MODEL_GPT_5_NANO_MEDIUM = deepcopy(MODEL_GPT_5_NANO_HIGH)
MODEL_GPT_5_NANO_MEDIUM["model_kwargs"]["reasoning_effort"] = "medium"
MODEL_GPT_5_MEDIUM = {
    "model_name": "openai/gpt-5-2025-08-07",
    "model_kwargs": {
        "drop_params": True,
        "api_key": OPENAI_API_KEY,
        "reasoning_effort": "medium",
    },
}
MODEL_GPT_5_HIGH = deepcopy(MODEL_GPT_5_MEDIUM)
MODEL_GPT_5_HIGH["model_kwargs"]["reasoning_effort"] = "high"

MODEL_GPT5_CODEX = deepcopy(MODEL_GPT_5_MEDIUM)
MODEL_GPT5_CODEX["model_name"] = "openai/gpt-5-codex"

MODEL_GPT5_CODEX_MINI = deepcopy(MODEL_GPT_5_MEDIUM)
MODEL_GPT5_CODEX_MINI["model_name"] = "openai/gpt-5.1-codex-mini"

MODEL_GPT5_2_CODEX = deepcopy(MODEL_GPT_5_MEDIUM)
MODEL_GPT5_2_CODEX["model_name"] = "openai/gpt-5.2-codex"

################
# OPENROUTER   #
################

MODEL_CODEX_MINI_OR = {
    "model_name": "openrouter/openai/gpt-4.1-mini",
    "model_kwargs": {
        "drop_params": True,
        "api_key": OPENROUTER_API_KEY,
    },
}


###########
# GPT OSS #
###########

MODEL_GPT_OSS_120B_HIGH = {
    "model_name": "hosted_vllm/openai/gpt-oss-120b",
    "api_base": "http://localhost:4001/v1",
    "model_kwargs": {
        "drop_params": True,
        "temperature": 0.7,
        "reasoning_effort": "high",
    },
}

MODEL_GPT_OSS_120B_MEDIUM = deepcopy(MODEL_GPT_OSS_120B_HIGH)
MODEL_GPT_OSS_120B_MEDIUM["model_kwargs"]["reasoning_effort"] = "medium"

MODEL_GPTOSS_20B_HIGH = deepcopy(MODEL_GPT_OSS_120B_HIGH)
MODEL_GPTOSS_20B_HIGH["model_name"] = "hosted_vllm/openai/gpt-oss-20b"


###############
# QWEN MODELS #
###############

MODEL_QWEN3_30B_CODER = {
    "model_name": "hosted_vllm/Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8",
    "api_base": "http://localhost:4000/v1",
    "model_kwargs": {
        "drop_params": True,
        "temperature": 0.7,
        "top_p": 0.8,
        "api_key": "anything",
        "stream": False,
        "max_completion_tokens": 4096,
    },
}

ALL_MODEL_CONFIGS = {
    "gpt-5-mini-high": MODEL_GPT_5_MINI_HIGH,
    "gpt-5-mini-medium": MODEL_GPT_5_MINI_MEDIUM,
    "gpt-5-nano-high": MODEL_GPT_5_NANO_HIGH,
    "gpt-5-nano-medium": MODEL_GPT_5_NANO_MEDIUM,
    "gpt-5-medium": MODEL_GPT_5_MEDIUM,
    "gpt-5-high": MODEL_GPT_5_HIGH,
    "gpt-oss-120b-high": MODEL_GPT_OSS_120B_HIGH,
    "gpt-oss-120b-medium": MODEL_GPT_OSS_120B_MEDIUM,
    "gpt-oss-20b-high": MODEL_GPTOSS_20B_HIGH,
    "gpt-5-codex": MODEL_GPT5_CODEX,
    "qwen3-30b-coder": MODEL_QWEN3_30B_CODER,
    "opus-4-5": MODEL_OPUS,
    "sonnet-4-5": MODEL_SONNET,
    "gpt-5.1-codex-mini": MODEL_GPT5_CODEX_MINI,
    "gpt-5.2-codex": MODEL_GPT5_2_CODEX,
    "gemini-3-flash": MODEL_GEMINI_FLASH,
    "codex-mini-or": MODEL_CODEX_MINI_OR,
}
