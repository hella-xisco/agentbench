HOST=$1
PORT=$2

# ⚠️ PLATZHALTER (19.07.) — vor dem ersten Lauf auf dem Hundhammer-Server verifizieren:
# - Exakter HF-Checkpoint/Quant (VRAM-Fit, Multi-GPU-Split je nach Anzahl H100)
# - Ob "glm45" noch der richtige --tool-call-parser/--reasoning-parser-Name ist
#   (vLLM-Support für GLM-4.5 nutzt diese Namen; für GLM-5.2 ggf. anders)
vllm serve zai-org/GLM-5.2 \
  --dtype auto \
  --port $PORT \
  --host $HOST \
  --enable-auto-tool-choice \
  --tool-call-parser glm45 \
  --reasoning-parser glm45 \
  --enable-chunked-prefill \
  --async-scheduling
