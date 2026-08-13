#!/usr/bin/env bash
# Fährt mehrere Runs (Zellen) ab — je Zelle generate -> evaluate, mehrere Zellen
# wahlweise parallel. Gedacht für Kalibrierung (2 Zellen), Matrix-Run (6 Zellen)
# und Varianz-Pilot (viele run_ids).
#
# Zellen-Datei: eine Zelle pro Zeile, TAB-getrennt, '#' = Kommentar
#   run_id <TAB> exec_model <TAB> generator <TAB> plan_type <TAB> filter_spec
#
# Beispiel (cells.tsv):
#   2026-08-13_01-kalib-qwen-cc	qwen3-30b-coder-t0	claude_code	no_plan	^(a|b)$
#   2026-08-13_02-kalib-kimi-cc	kimi-k2.7-code	claude_code	no_plan	^(a|b)$
#
# Verwendung:
#   scripts/run_batch.sh cells.tsv --dry-run          # nur zeigen, nichts tun
#   scripts/run_batch.sh cells.tsv                    # sequenziell (Default)
#   scripts/run_batch.sh cells.tsv --jobs 2           # 2 Zellen parallel
#   scripts/run_batch.sh cells.tsv --workers 4        # 4 Instanzen parallel je Zelle
#
# WICHTIG bei --jobs > 1:
#   * Jede Zelle bekommt einen eigenen LiteLLM-Port (Basis + Index*10). Der Proxy
#     sucht sich KEINEN freien Port — ohne eigene Ports redet Zelle B mit dem
#     Proxy von Zelle A und misst still das falsche Modell.
#   * Alle Zellen mit lokalem Modell teilen sich dieselbe vLLM-Instanz. Die
#     gleichzeitige Last ist jobs × workers Agenten. Container-Last ebenso:
#     jobs × workers Container à --cpus (siehe docker.py `_default_run_args`).
set -uo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CELLS_FILE="${1:?Verwendung: run_batch.sh <cells.tsv> [--jobs N] [--workers N] [--dry-run] [--skip-eval]}"
shift

JOBS=1
WORKERS=2
PORT_BASE=18080
DRY_RUN=0
SKIP_EVAL=0
OUT_ROOT="${RUNS_DIR:-$HOME/runs}"
DATASET="eth-sri/agentbench"
BENCHMARK="agentbench"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --jobs)      JOBS="$2"; shift 2 ;;
    --workers)   WORKERS="$2"; shift 2 ;;
    --port-base) PORT_BASE="$2"; shift 2 ;;
    --dry-run)   DRY_RUN=1; shift ;;
    --skip-eval) SKIP_EVAL=1; shift ;;
    *) echo "unbekannte Option: $1" >&2; exit 2 ;;
  esac
done

[[ -f "$CELLS_FILE" ]] || { echo "FEHLER: $CELLS_FILE nicht gefunden" >&2; exit 2; }

# --- Zellen einlesen + validieren -------------------------------------------
declare -a RUN_IDS MODELS GENERATORS PLANS FILTERS
while IFS=$'\t' read -r run_id exec_model generator plan_type filter_spec || [[ -n "${run_id:-}" ]]; do
  [[ -z "${run_id// }" || "${run_id:0:1}" == "#" ]] && continue
  if [[ -z "${exec_model:-}" || -z "${generator:-}" || -z "${plan_type:-}" || -z "${filter_spec:-}" ]]; then
    echo "FEHLER: unvollständige Zeile (5 TAB-getrennte Felder erwartet): $run_id" >&2; exit 2
  fi
  RUN_IDS+=("$run_id"); MODELS+=("$exec_model"); GENERATORS+=("$generator")
  PLANS+=("$plan_type"); FILTERS+=("$filter_spec")
done < "$CELLS_FILE"

N=${#RUN_IDS[@]}
(( N > 0 )) || { echo "FEHLER: keine Zellen in $CELLS_FILE" >&2; exit 2; }

# doppelte run_ids => Artefakte würden sich überschreiben
dupes=$(printf '%s\n' "${RUN_IDS[@]}" | sort | uniq -d)
[[ -z "$dupes" ]] || { echo "FEHLER: doppelte run_id(s):"$'\n'"$dupes" >&2; exit 2; }

echo "Zellen: $N · parallel: $JOBS · workers je Zelle: $WORKERS"
echo "Spitzenlast: $((JOBS * WORKERS)) gleichzeitige Agenten/Container"
echo

run_cell() {
  local i="$1"
  local run_id="${RUN_IDS[$i]}" model="${MODELS[$i]}" gen="${GENERATORS[$i]}"
  local plan="${PLANS[$i]}" filter="${FILTERS[$i]}"
  local port=$((PORT_BASE + i * 10))
  local outdir="${OUT_ROOT}/${run_id}"
  local log="${outdir}/driver.log"

  local common=(--plan_type "$plan" --exec_model "$model" --generator "$gen"
                --benchmark "$BENCHMARK" --dataset_name "$DATASET"
                --output_dir "$outdir")

  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[$run_id] generate (port $port):"
    echo "  python scripts/agentbench/run_harness/generate.py ${common[*]} --filter_spec '$filter' --workers $WORKERS --port $port"
    [[ "$SKIP_EVAL" == "1" ]] || echo "  python scripts/agentbench/run_harness/evaluate.py ${common[*]} --workers $WORKERS"
    return 0
  fi

  mkdir -p "$outdir"
  echo "[$run_id] start  · modell=$model harness=$gen port=$port · log=$log"

  if ! python "${REPO_DIR}/scripts/agentbench/run_harness/generate.py" \
        "${common[@]}" --filter_spec "$filter" --workers "$WORKERS" --port "$port" >>"$log" 2>&1; then
    echo "[$run_id] FEHLER in generate — siehe $log"
    return 1
  fi

  if [[ "$SKIP_EVAL" != "1" ]]; then
    # evaluate braucht kein Modell (nur Patches + Tests) -> kein Port nötig
    if ! python "${REPO_DIR}/scripts/agentbench/run_harness/evaluate.py" \
          "${common[@]}" --workers "$WORKERS" >>"$log" 2>&1; then
      echo "[$run_id] FEHLER in evaluate — siehe $log"
      return 1
    fi
  fi

  echo "[$run_id] fertig"
  return 0
}

# --- abarbeiten, max. $JOBS gleichzeitig ------------------------------------
declare -a PIDS=() PID_CELL=()
FAILED=0

for (( i=0; i<N; i++ )); do
  while (( $(jobs -rp | wc -l) >= JOBS )); do wait -n || FAILED=1; done
  run_cell "$i" &
  PIDS+=("$!"); PID_CELL+=("${RUN_IDS[$i]}")
done

for idx in "${!PIDS[@]}"; do
  if ! wait "${PIDS[$idx]}"; then
    echo "fehlgeschlagen: ${PID_CELL[$idx]}" >&2
    FAILED=1
  fi
done

echo
if (( FAILED )); then
  echo "FERTIG MIT FEHLERN — Logs in ${OUT_ROOT}/<run_id>/driver.log"
  exit 1
fi
echo "alle $N Zellen fertig. Artefakte: ${OUT_ROOT}/<run_id>/ — lokal holen mit scripts/run_pull.sh <run_id>"
