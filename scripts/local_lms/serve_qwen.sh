#!/usr/bin/env bash
# Lebenszyklus des lokalen vLLM-Servers — expliziter Start/Stop statt "läuft halt".
# Auf einer geteilten Maschine soll die GPU nur belegt sein, solange gemessen wird.
#
#   serve_qwen.sh start           vLLM in tmux starten und auf Bereitschaft warten
#   serve_qwen.sh status          läuft er? welcher Zustand? wie viel VRAM?
#   serve_qwen.sh wait            blockiert, bis der Server Requests annimmt
#   serve_qwen.sh stop            tmux-Session beenden, VRAM freigeben
#   serve_qwen.sh sleep           Gewichte+KV-Cache freigeben, Prozess bleibt (Level 1)
#   serve_qwen.sh wake            aus dem Sleep zurückholen
#   serve_qwen.sh watchdog 30     im Hintergrund: nach 30 min ohne Requests -> sleep
#
# Env: GPU (Default 2) · PORT (4000) · GPU_MEM_UTIL (0.85) · TOOL_PARSER (qwen3_xml)
#      SESSION (vllm) · LOG_DIR ($HOME/runs/_serving)
#
# Sleep/Wake brauchen VLLM_SERVER_DEV_MODE=1 beim Start (setzt `start` automatisch)
# und --enable-sleep-mode. Quelle: docs.vllm.ai/en/latest/features/sleep_mode/
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
GPU="${GPU:-2}"
PORT="${PORT:-4000}"
SESSION="${SESSION:-vllm}"
LOG_DIR="${LOG_DIR:-$HOME/runs/_serving}"
BASE="http://localhost:${PORT}"

_running()  { tmux has-session -t "$SESSION" 2>/dev/null; }
_healthy()  { curl -sf "${BASE}/health" >/dev/null 2>&1; }
_asleep()   { curl -sf "${BASE}/is_sleeping" 2>/dev/null | grep -q 'true'; }

cmd_start() {
  if _running; then echo "tmux-Session '$SESSION' läuft bereits — 'stop' zuerst, oder 'status'."; exit 1; fi
  mkdir -p "$LOG_DIR"
  local log="${LOG_DIR}/vllm_qwen_$(date +%F_%H%M).log"
  echo "starte vLLM · GPU $GPU · Port $PORT · Log $log"
  tmux new-session -d -s "$SESSION" \
    "source ~/vllm-venv/bin/activate && \
     export HF_HOME=\$HOME/.cache/huggingface CUDA_VISIBLE_DEVICES=$GPU VLLM_SERVER_DEV_MODE=1 && \
     bash '${HERE}/vllm_qwen.sh' 0.0.0.0 $PORT --enable-sleep-mode 2>&1 | tee '$log'"
  cmd_wait
}

cmd_wait() {
  echo -n "warte auf Bereitschaft"
  for _ in $(seq 1 180); do            # bis 15 min: Laden + CUDA-Graph
    if _healthy; then echo " — bereit."; return 0; fi
    if ! _running; then echo; echo "FEHLER: Session weg, Start fehlgeschlagen. Log in $LOG_DIR" >&2; return 1; fi
    echo -n "."; sleep 5
  done
  echo; echo "FEHLER: nach 15 min nicht bereit — Log prüfen." >&2; return 1
}

cmd_status() {
  if ! _running;  then echo "vLLM: gestoppt (keine tmux-Session '$SESSION')"; return 0; fi
  if _asleep;     then echo "vLLM: SLEEP (Prozess lebt, VRAM freigegeben)";
  elif _healthy;  then echo "vLLM: bereit auf $BASE";
  else                 echo "vLLM: Session läuft, antwortet noch nicht (startet?)"; fi
  nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader | sed 's/^/  GPU /'
}

cmd_stop()  { _running && tmux kill-session -t "$SESSION" && echo "gestoppt, VRAM frei." || echo "lief nicht."; }
cmd_sleep() { curl -sf -X POST "${BASE}/sleep?level=1" >/dev/null && echo "schläft (Level 1)." || { echo "sleep fehlgeschlagen" >&2; exit 1; }; }
cmd_wake()  { curl -sf -X POST "${BASE}/wake_up"      >/dev/null && echo "wach."          || { echo "wake fehlgeschlagen" >&2; exit 1; }; }

# Inaktivität über die Prometheus-Metriken erkennen: laufende + wartende Requests.
# Kein Dev-Mode nötig zum Messen, nur zum Schlafenlegen.
cmd_watchdog() {
  local idle_min="${1:-30}" checks=$(( ${1:-30} )) strikes=0
  echo "Watchdog: schlafen legen nach ${idle_min} min ohne Requests (Prüfung jede Minute)"
  while _running; do
    if _asleep; then strikes=0; sleep 60; continue; fi
    local busy
    busy=$(curl -sf "${BASE}/metrics" 2>/dev/null \
           | awk '/^vllm:num_requests_(running|waiting)/ {s+=$2} END {print s+0}')
    if [[ "${busy:-0}" == "0" ]]; then strikes=$((strikes+1)); else strikes=0; fi
    if (( strikes >= checks )); then
      echo "$(date +%F_%T) — ${idle_min} min idle, lege schlafen"
      cmd_sleep || true
      strikes=0
    fi
    sleep 60
  done
  echo "Watchdog beendet (Server gestoppt)."
}

case "${1:-}" in
  start)    cmd_start ;;
  wait)     cmd_wait ;;
  status)   cmd_status ;;
  stop)     cmd_stop ;;
  sleep)    cmd_sleep ;;
  wake)     cmd_wake ;;
  watchdog) shift; cmd_watchdog "${1:-30}" ;;
  *) sed -n '2,20p' "$0"; exit 2 ;;
esac
