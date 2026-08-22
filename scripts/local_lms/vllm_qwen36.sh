#!/usr/bin/env bash
# Serviert Qwen3.6-27B-FP8 über vLLM (OpenAI-kompatibel) auf EINER H100.
# Zweites Modell der Studie (RQ4-Reserve, Beschluss 22.08.2026).
#
# Verwendung:  vllm_qwen36.sh <host> <port> [weitere vllm-Flags...]
#   Instanz A: export CUDA_VISIBLE_DEVICES=2 && vllm_qwen36.sh 0.0.0.0 4002
#   Instanz B: export CUDA_VISIBLE_DEVICES=3 && vllm_qwen36.sh 0.0.0.0 4003
#
# Env-Overrides (geteilter Server -> bewusst konservative Defaults):
#   GPU_MEM_UTIL   Anteil des VRAM, den vLLM belegen darf (Default 0.85)
#   MAX_LEN        --max-model-len (Default 131072; nativ 262144, 128k reicht bei
#                  4 parallelen Agenten mit Pi-Compaction und spart KV-Cache)
#
# Parser-Flags laut Model-Card (huggingface.co/Qwen/Qwen3.6-27B): tool-call-parser
# qwen3_coder, reasoning-parser qwen3. Hybrid-Thinking bleibt AN (Paritaet zu
# GLM-4.5-Air, offene-entscheidungen #10). temp 0 kommt aus der Registry
# (qwen3.6-27b-t0), nicht von hier.
set -euo pipefail

# Hundhammer hat kein CUDA-Toolkit (kein nvcc/ptxas) — FlashInfer-Sampler aus
# (Details: vllm_qwen.sh).
export VLLM_USE_FLASHINFER_SAMPLER="${VLLM_USE_FLASHINFER_SAMPLER:-0}"

HOST="${1:?Verwendung: vllm_qwen36.sh <host> <port> [vllm-Flags...]}"
PORT="${2:?Verwendung: vllm_qwen36.sh <host> <port> [vllm-Flags...]}"
shift 2

vllm serve Qwen/Qwen3.6-27B-FP8 \
  --dtype auto \
  --port "$PORT" \
  --host "$HOST" \
  --tensor-parallel-size 1 \
  --max-model-len "${MAX_LEN:-131072}" \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --reasoning-parser qwen3 \
  --enable-chunked-prefill \
  --gpu-memory-utilization "${GPU_MEM_UTIL:-0.85}" \
  --served-model-name qwen3.6-27b-fp8 \
  "$@"
