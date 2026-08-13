#!/usr/bin/env bash
# Serviert Qwen3-Coder-30B-A3B-FP8 über vLLM (OpenAI-kompatibel).
#
# Verwendung:  vllm_qwen.sh <host> <port> [weitere vllm-Flags...]
#   z. B.      vllm_qwen.sh 0.0.0.0 4000
#              vllm_qwen.sh 0.0.0.0 4000 --max-model-len 131072
#
# Env-Overrides (geteilter Server -> bewusst konservative Defaults):
#   GPU_MEM_UTIL   Anteil des VRAM, den vLLM belegen darf (Default 0.85)
#   TOOL_PARSER    Tool-Call-Parser (Default qwen3_xml; Fallback qwen3_coder)
#
# GPU-Auswahl über CUDA_VISIBLE_DEVICES, NICHT hier:
#   export CUDA_VISIBLE_DEVICES=2 && vllm_qwen.sh 0.0.0.0 4000
set -euo pipefail

HOST="${1:?Verwendung: vllm_qwen.sh <host> <port> [vllm-Flags...]}"
PORT="${2:?Verwendung: vllm_qwen.sh <host> <port> [vllm-Flags...]}"
shift 2

vllm serve Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8 \
  --dtype auto \
  --port "$PORT" \
  --host "$HOST" \
  --enable-auto-tool-choice \
  --tool-call-parser "${TOOL_PARSER:-qwen3_xml}" \
  --enable-chunked-prefill \
  --async-scheduling \
  --gpu-memory-utilization "${GPU_MEM_UTIL:-0.85}" \
  "$@"
