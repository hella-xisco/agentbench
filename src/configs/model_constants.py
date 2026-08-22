import os
from copy import deepcopy

##### API KEYS #####

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY")


#### Costs

# input, output, cache, cache_creation
MODEL_PRICES = {
    "Qwen3-Coder-30B-A3B-Instruct-FP8": (0.1, 0.3, 0.0, 0.0),
    # Moonshot-Listenpreise (recherchiert 13.08.2026, Quellen im Decisions-Log)
    "kimi-k2.5": (0.6, 3.0, 0.1, 0.0),
    "kimi-k2.7-code": (0.95, 4.0, 0.19, 0.0),
    "GLM-5.2": (0.0, 0.0, 0.0, 0.0),  # local/free — placeholder, adjust if pricing ever matters
    "claude-haiku-4-5-20251001": (1.0, 5.0, 0.10, 1.25),
    "claude-sonnet-4-5-20250929": (3.0, 15.0, 0.3, 3.75),
    # Sonnet-5-Listenpreis; Aktionspreis 2.0/10.0 laeuft bis 31.08.2026
    "claude-sonnet-5": (3.0, 15.0, 0.3, 3.75),
    "claude-sonnet-4-6": (3.0, 15.0, 0.3, 3.75),
    "gpt-5-codex": (1.25, 10.0, 0.125, 0.0),
    "gpt-5.1-codex-mini": (0.25, 2.0, 0.025, 0.0),
    "gpt-5-mini-2025-08-07": (0.25, 2.0, 0.02, 0.0),
    "gpt-5.2-codex": (1.75, 14.0, 0.175, 0.0),
    "gemini-3-flash-preview": (0.25, 1.5, 0.05, 0.0),
    # OpenRouter-Routen: Provider-Listenpreise; OR-Fee (~5 %) faellt beim
    # Guthabenkauf an, nicht pro Token -- Logging nutzt Listenpreise
    "openrouter/moonshotai/kimi-k2.7-code": (0.95, 4.0, 0.19, 0.0),
    "openrouter/anthropic/claude-sonnet-4.6": (3.0, 15.0, 0.3, 3.75),
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

# Proprietaerer Referenzpunkt, EMPFOHLENE Variante (13.08.):
# Sonnet 4.6 statt Sonnet 5, aus zwei Gruenden —
#   1. Leistungsklasse naeher an kimi-k2.7-code (SWE-V 79.6 % vs. Sonnet 5 85.2 %;
#      Kimi-Nachfolger von K2.5 @ 76.8 % Moonshot-Eigenangabe) => vergleichbarer
#      Referenzpunkt statt Ausreisser nach oben.
#   2. akzeptiert temperature=0 => protokollkonsistent zu Qwen/Kimi.
MODEL_SONNET_4_6 = {
    "model_name": "anthropic/claude-sonnet-4-6",
    "model_kwargs": {
        "drop_params": True,
        "temperature": 0.0,
        "api_key": ANTHROPIC_API_KEY,
    },
}

# Proprietaerer Referenzpunkt (13.08.): aktuelles Sonnet-Coding-Modell.
#
# ⚠️ KEIN temperature-Feld — Sonnet 5 lehnt nicht-default temperature/top_p/top_k
# mit 400 ab. Diese Zelle laeuft also zwangslaeufig im As-shipped-Sampling-Regime,
# nicht bei temp 0 wie der Rest des Protokolls. Als Limitation berichten.
# Temp-0-faehige Alternativen derselben Familie: claude-sonnet-4-6 (gleicher Preis,
# eine Generation aelter) oder claude-haiku-4-5 (billiger, naeher an Kimi-K2.7-Preis).
#
# Ausserdem: Sonnet 5 denkt per Default adaptiv (thinking-Feld weggelassen = an) —
# das verbraucht Output-Budget. max_completion_tokens grosszuegig lassen.
MODEL_SONNET_5 = {
    "model_name": "anthropic/claude-sonnet-5",
    "model_kwargs": {
        "drop_params": True,
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

# OpenRouter ist ein Router: dasselbe Modell kann je nach Lage von verschiedenen
# Hostern (teils in anderer Quantisierung) bedient werden -- fuer eine Messung ist
# der Modellname allein deshalb kein ausreichender Identifikator. Beide Eintraege
# pinnen den Provider hart: allow_fallbacks=False laesst den Request LAUT scheitern,
# statt still einen anderen Hoster zu messen. Der tatsaechlich bedienende Provider
# steht in jeder OpenRouter-Response und wird im Smoke verifiziert.
# (Modell-Slugs beim Smoke gegen /v1/models pruefen -- Stand 15.08.2026 unverifiziert.)

MODEL_KIMI_K27_CODE_OR = {
    "model_name": "openrouter/moonshotai/kimi-k2.7-code",
    "model_kwargs": {
        "drop_params": True,
        "temperature": 0.0,
        "api_key": OPENROUTER_API_KEY,
        "extra_body": {"provider": {"order": ["moonshotai"], "allow_fallbacks": False}},
    },
}

MODEL_SONNET_4_6_OR = {
    "model_name": "openrouter/anthropic/claude-sonnet-4.6",
    "model_kwargs": {
        "drop_params": True,
        "temperature": 0.0,   # Sonnet 4.6 akzeptiert temp 0 (anders als Sonnet 5)
        "api_key": OPENROUTER_API_KEY,
        "extra_body": {"provider": {"order": ["anthropic"], "allow_fallbacks": False}},
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


##########################
# MOONSHOT / KIMI (API)  #
##########################

# OpenAI-kompatibler Endpoint (LiteLLM spricht ihn über den openai/-Provider an);
# Anthropic-kompatibel waere https://api.moonshot.ai/anthropic — brauchen wir hier
# nicht, weil der Harness ohnehin einen LiteLLM-Proxy davorsetzt.
#
# ACHTUNG kimi-k2.5: Moonshot hat eine Retirement-Notice zum 31.08.2026 veroeffentlicht.
# Fuer Kalibrierung im August nutzbar, als Studienmodell fuer Pilot/Hauptlauf NICHT —
# dafuer ist kimi-k2.7-code der coding-tuned Nachfolger.
MODEL_KIMI_K25 = {
    "model_name": "openai/kimi-k2.5",
    "api_base": "https://api.moonshot.ai/v1",
    "model_kwargs": {
        "drop_params": True,
        "temperature": 0.0,
        "api_key": MOONSHOT_API_KEY,
        "stream": False,
        "max_completion_tokens": 4096,
    },
}

MODEL_KIMI_K27_CODE = deepcopy(MODEL_KIMI_K25)
MODEL_KIMI_K27_CODE["model_name"] = "openai/kimi-k2.7-code"


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

# Studien-Variante (Smoke/Pilot/Hauptlauf, seit 08.08.): identischer Checkpoint,
# aber temp 0 gemäß Protokoll (ETH-Replikation) statt der Qwen-Sampling-Empfehlung
# (0.7/0.8, oben) — Abweichung bewusst, als Limitation dokumentiert.
MODEL_QWEN3_30B_CODER_T0 = {
    "model_name": "hosted_vllm/Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8",
    "api_base": "http://localhost:4000/v1",
    "model_kwargs": {
        "drop_params": True,
        "temperature": 0.0,
        "api_key": "anything",
        "stream": False,
        "max_completion_tokens": 4096,
    },
}

##########################
# GLM (lokal, Hundhammer) #
##########################

# Laufmodell der Studie (Pivot §12, seit 16.08. produktiv auf dem Server):
# GLM-4.5-Air-FP8 via vLLM auf GPU 2+3, TP=2, Port 4001, --served-model-name
# glm-4.5-air-fp8, Parser glm45 (scripts/local_lms/vllm_glm.sh). temp 0 gemäß
# ETH-Protokoll; Determinismus am 16.08. per Doppel-Request verifiziert (inkl.
# identischem Reasoning-Text). ⚠️ Hybrid-Reasoning: Thinking ist per
# Serving-Default AN (offene-entscheidungen #10 — Default belassen, dokumentieren);
# max_completion_tokens deshalb großzügiger als bei Qwen (Reasoning zählt mit).
MODEL_GLM_45_AIR_T0 = {
    "model_name": "hosted_vllm/glm-4.5-air-fp8",
    "api_base": "http://localhost:4001/v1",
    "model_kwargs": {
        "drop_params": True,
        "temperature": 0.0,
        "api_key": "anything",
        "stream": False,
        "max_completion_tokens": 8192,
    },
}

# Zweites Modell der Studie — RQ4-Reserve (Beschluss 22.08., Erweiterung nach dem
# Design-Freeze, Decisions-Log 22.08.): Qwen3.6-27B-FP8 (dense, Apache 2.0) via vLLM
# auf EINER H100, Parser qwen3_coder + reasoning-parser qwen3 (Model-Card-Kommando),
# --served-model-name qwen3.6-27b-fp8 (scripts/local_lms/vllm_qwen36.sh).
# Zwei Instanzen (GPU 2 -> Port 4002, GPU 3 -> Port 4003), je Treiber 4 Worker =
# gleiche Last je Engine wie bei GLM (Varianz-Parameter). Der Port wird per
# generate.py --exec_model_api_base je Treiber gesetzt (run_0 -> 4002, run_1 -> 4003);
# Default hier = 4002. Hybrid-Thinking bleibt AN (Paritaet zu GLM-4.5-Air, #10);
# temp 0 statt der empfohlenen 0.6 (Protokollkonstanz, ETH).
# max_completion_tokens 32768 (NICHT 8192 wie GLM): Smoke 22.08. zeigte in 2/6 Zellen
# ein mitten im Gedanken abgeschnittenes Reasoning (39k Zeichen, kein Loop) -> leerer
# Content, kein Tool-Call -> Lauf endet wie No-Action. Das Cap ist eine technische
# Obergrenze, kein Treatment, und darf nicht binden (Cap-Regel, Decisions-Log 22.08.);
# Schutz vor Endlos-Denken bleibt das Timeout 660 s (#27), identisch fuer beide Modelle.
MODEL_QWEN36_27B_T0 = {
    "model_name": "hosted_vllm/qwen3.6-27b-fp8",
    "api_base": "http://localhost:4002/v1",
    "model_kwargs": {
        "drop_params": True,
        "temperature": 0.0,
        "api_key": "anything",
        "stream": False,
        "max_completion_tokens": 32768,
    },
}

# LAUFMODELL-EINTRAG Modell 2 (Beschluss Francisco 23.08., ~02:00): Hersteller-
# Dekodierung statt temp 0. Befund: bei temp 0 (greedy) geraet Qwen3.6 in
# deterministische Reasoning-Schleifen (K2 x openai-agents-1798: ein Absatz 113x
# wiederholt, 32k Tokens, kein Tool-Call) — die Model-Card warnt explizit vor Greedy
# Decoding. Loesung analog ETH ("as shipped"): temperature 0.6, top_p 0.95, top_k 20
# laut Model-Card. Konsequenz: kein Determinismus mehr => Varianz fuer DIESE
# Konfiguration per VP (10 Tasks x k=20) vor der Matrix gemessen; r=2 in der Matrix.
# Der t0-Eintrag oben bleibt als Beleg des Befunds (Smoke run_90-93).
MODEL_QWEN36_27B_T06 = {
    "model_name": "hosted_vllm/qwen3.6-27b-fp8",
    "api_base": "http://localhost:4002/v1",
    "model_kwargs": {
        "drop_params": True,
        "temperature": 0.6,
        "top_p": 0.95,
        "extra_body": {"top_k": 20},
        "api_key": "anything",
        "stream": False,
        "max_completion_tokens": 32768,
    },
}

# ⚠️ OBSOLET (16.08.): GLM-5.2-Plan-A wurde aufgehoben (753B passt nie auf
# 2xH100, Pivot §10); Eintrag bleibt nur als Historie, nicht verwenden.
MODEL_GLM_5_2 = {
    "model_name": "hosted_vllm/zai-org/GLM-5.2",  # TODO: exakte Repo-ID/Quant bestätigen
    "api_base": "http://localhost:4002/v1",
    "model_kwargs": {
        "drop_params": True,
        "temperature": 0.0,  # ETH-Protokoll — im Varianz-Piloten verifizieren wie bei codex-mini
        "api_key": "anything",
        "stream": False,
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
    "qwen3-30b-coder-t0": MODEL_QWEN3_30B_CODER_T0,
    "kimi-k2.5": MODEL_KIMI_K25,
    "kimi-k2.7-code": MODEL_KIMI_K27_CODE,
    "glm-4.5-air-t0": MODEL_GLM_45_AIR_T0,
    "qwen3.6-27b-t0": MODEL_QWEN36_27B_T0,
    "qwen3.6-27b-t06": MODEL_QWEN36_27B_T06,
    "glm-5.2": MODEL_GLM_5_2,  # obsolet, s. Kommentar oben
    "opus-4-5": MODEL_OPUS,
    "sonnet-4-5": MODEL_SONNET,
    "sonnet-4-6": MODEL_SONNET_4_6,
    "kimi-k2.7-code-or": MODEL_KIMI_K27_CODE_OR,
    "sonnet-4-6-or": MODEL_SONNET_4_6_OR,
    "sonnet-5": MODEL_SONNET_5,
    "gpt-5.1-codex-mini": MODEL_GPT5_CODEX_MINI,
    "gpt-5.2-codex": MODEL_GPT5_2_CODEX,
    "gemini-3-flash": MODEL_GEMINI_FLASH,
    "codex-mini-or": MODEL_CODEX_MINI_OR,
}
