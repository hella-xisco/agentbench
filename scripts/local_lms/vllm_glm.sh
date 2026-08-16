#!/usr/bin/env bash
# Serviert GLM-4.5-Air-FP8 über vLLM (OpenAI-kompatibel), Tensor-Parallel über 2 GPUs.
#
# Verwendung:  vllm_glm.sh <host> <port> [weitere vllm-Flags...]
#   z. B.      export CUDA_VISIBLE_DEVICES=0,1 && vllm_glm.sh 0.0.0.0 4001
#
# Env-Overrides (geteilter Server -> bewusst konservative Defaults):
#   GPU_MEM_UTIL   Anteil des VRAM, den vLLM belegen darf (Default 0.85)
#   TP_SIZE        Tensor-Parallel-Groesse (Default 2 — GLM-4.5-Air-FP8 braucht ~110 GB Gewichte)
#
# Parser-Flags laut offizieller zai-org-Doku (GLM-4.5-Repo): tool-call-parser glm45,
# reasoning-parser glm45 (GLM-4.5-Air ist Hybrid-Reasoning — Thinking per Default AN;
# Modus-Doku/Entscheidung: offene-entscheidungen #10).
set -euo pipefail

# Hundhammer hat kein CUDA-Toolkit (kein nvcc/ptxas) — nur den Treiber. JIT-Pfade
# scheitern deshalb; FlashInfer-Sampler abschalten (Details: vllm_qwen.sh).
export VLLM_USE_FLASHINFER_SAMPLER="${VLLM_USE_FLASHINFER_SAMPLER:-0}"

HOST="${1:?Verwendung: vllm_glm.sh <host> <port> [vllm-Flags...]}"
PORT="${2:?Verwendung: vllm_glm.sh <host> <port> [vllm-Flags...]}"
shift 2

vllm serve zai-org/GLM-4.5-Air-FP8 \
  --dtype auto \
  --port "$PORT" \
  --host "$HOST" \
  --tensor-parallel-size "${TP_SIZE:-2}" \
  --enable-auto-tool-choice \
  --tool-call-parser glm45 \
  --reasoning-parser glm45 \
  --enable-chunked-prefill \
  --gpu-memory-utilization "${GPU_MEM_UTIL:-0.85}" \
  --served-model-name glm-4.5-air-fp8 \
  "$@"
