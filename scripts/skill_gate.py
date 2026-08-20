#!/usr/bin/env python3
"""Skill-Gate — reproduzierbares Delivery-Experiment fuer Agent-Konfigurationen.

Prueft fuer EINE Harness-x-Modell-Konfiguration, ob Agent Skills und Kontextdateien
(AGENTS.md/CLAUDE.md) tatsaechlich ausgeliefert werden — insbesondere, ob der Agent
einen passenden Skill SPONTAN aktiviert (Progressive Disclosure, Ein-Skill-Fall).

Herkunft: Experiment 2026-08-16_02-machbarkeit-glm-skills (Thesis-Repo, setup-log.md
dort dokumentiert die manuelle Urform samt Ergebnissen). Dieses Script automatisiert
das Protokoll, damit das Gate auf jeder Konfiguration in <1 h nachfahrbar ist.

Messmethode (Marker-Technik, zwei Beweiskanaele):
  - Kontext-Marker (Default ORAKEL) steht NUR in AGENTS.md/CLAUDE.md
    -> faellt er, wurde die Kontextdatei geladen und befolgt (upfront-Kanal).
  - Skill-Marker (Default KOLIBRI) steht NUR im SKILL.md-Body, nicht in den
    Frontmatter-Metadaten -> faellt er, hat der Skill-Body nachweislich den
    Modell-Kontext erreicht UND das Verhalten gesteuert (on-demand-Kanal).
  Marker sind harness-unabhaengige Verhaltens-Ground-Truth; Log-Forensik je
  Harness kommt als zweiter Kanal dazu (ausserhalb dieses Scripts).

Protokoll (13 frische Sessions):
  P1-P3   neutral      -> G1 Kontextdatei-Konsum (Kontext-Marker in >=2/3)
  P4-P8   relevant     -> G3 Spontan-Aktivierung (Skill-Marker in >=3/5)
  P9-P10  irrelevant   -> G4 Spezifitaet (Skill-Marker in 0/2)
  P11     = P4         -> G6 Wiederholbarkeit (gleiches Aktivierungs-Ergebnis)
  D1      Diagnose     -> G2 Discovery (Skill wird namentlich genannt)
  D2      Diagnose     -> MECH Lade-Mechanik (Skill-Marker bei expliziter Aufforderung)
  Laeufe ohne inhaltliche Ausgabe gelten als UNGUELTIG (No-Action/Leerlauf),
  nicht als Nicht-Aktivierung — sie werden separat gezaehlt und berichtet.

Verwendung (Beispiele; {prompt} wird shell-sicher ersetzt, cwd = Workspace):
  # Pi (direkt gegen vLLM/openai-kompatibel; temp 0 via models.json samplingParams):
  python3 scripts/skill_gate.py \
    --harness-cmd 'pi -p -a --provider vllm-local --model glm-4.5-air-fp8 {prompt}' \
    --label pi-glm --out ~/runs/skill_gate

  # Claude Code (via LiteLLM-Proxy; Env vorher setzen: ANTHROPIC_BASE_URL,
  # ANTHROPIC_AUTH_TOKEN, ANTHROPIC_MODEL, ANTHROPIC_SMALL_FAST_MODEL):
  python3 scripts/skill_gate.py \
    --harness-cmd 'claude -p --dangerously-skip-permissions {prompt}' \
    --label cc-glm --out ~/runs/skill_gate

Voraussetzungen: Harness-CLI installiert + auf das Zielmodell konfiguriert;
pytest fuer das Spiel-Repo im PATH-Python (python3 -m pytest).
Hinweis Reproduzierbarkeit: Der Workspace wird pro Lauf frisch aufgebaut
(P9 mutiert eine Datei); bei temp 0 ist das Protokoll deterministisch.
"""

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_NAME = "run-project-tests"

# Kategorien: neutral (G1) / relevant (G3) / irrelevant (G4) / repeat (G6) / diag (G2, MECH)
PROMPTS = [
    ("P1",  "neutral",    "Describe briefly how this project is structured."),
    ("P2",  "neutral",    "What files exist in this repository? Answer in one line."),
    ("P3",  "neutral",    "Summarize the purpose of this project in one sentence."),
    ("P4",  "relevant",   "Run the tests and report the results."),
    ("P5",  "relevant",   "Check whether the test suite passes and summarize the outcome."),
    ("P6",  "relevant",   "I think test_add might be flaky - can you verify the tests are reliable?"),
    ("P7",  "relevant",   "Make sure everything is green, I want to commit soon."),
    ("P8",  "relevant",   "Verify this project works as intended."),
    ("P9",  "irrelevant", "Add a short docstring to the add function in src/calc.py."),
    ("P10", "irrelevant", "What is 2 plus 3? Answer with just the number."),
    ("P11", "repeat",     "Run the tests and report the results."),
    ("D1",  "diag",       "List the agent skills available to you in this session, by name. "
                          "If none are available, say so explicitly."),
    ("D2",  "diag",       f"You have a skill called {SKILL_NAME}. Load and follow it, "
                          "then run the tests and report the results."),
]

CALC_PY = '''def add(a, b):
    return a + b

def sub(a, b):
    return a - b
'''

TEST_PY = '''from src.calc import add, sub

def test_add():
    assert add(2, 3) == 5

def test_sub():
    assert sub(5, 3) == 2
'''

CONFTEST_PY = '''import sys, os
sys.path.insert(0, os.path.dirname(__file__))
'''


def scaffold(ws: Path, ctx_marker: str, skill_marker: str) -> None:
    """Marker-Test-Repo frisch aufbauen (identisches Layout wie im Ur-Experiment)."""
    if ws.exists():
        shutil.rmtree(ws)
    (ws / "src").mkdir(parents=True)
    (ws / "tests").mkdir()
    (ws / "src" / "calc.py").write_text(CALC_PY)
    (ws / "tests" / "test_calc.py").write_text(TEST_PY)
    (ws / "conftest.py").write_text(CONFTEST_PY)

    agents_md = (
        "# Project notes for agents\n\n"
        f"- Always begin the very first line of your reply with the word {ctx_marker}: "
        "followed by your answer.\n"
        "- This is a small Python calculator utility. Source lives in src/, tests in tests/.\n"
    )
    (ws / "AGENTS.md").write_text(agents_md)
    (ws / "CLAUDE.md").write_text(agents_md)

    skill_md = (
        "---\n"
        f"name: {SKILL_NAME}\n"
        "description: How to correctly run and interpret this project's test suite\n"
        "---\n\n"
        "To run this project's tests, use exactly:\n\n"
        "    python3 -m pytest tests/ -q --tb=no\n\n"
        f"When you report test results in this project, always include the codeword {skill_marker}\n"
        "in your summary so maintainers can trace the report.\n"
    )
    # Alle bekannten Discovery-Pfade bestuecken; welcher greift, ist selbst ein Befund.
    for d in (".claude/skills", ".agents/skills", ".pi/skills"):
        p = ws / d / SKILL_NAME
        p.mkdir(parents=True)
        (p / "SKILL.md").write_text(skill_md)


def run_prompt(cmd_template: str, prompt: str, cwd: Path, timeout: int) -> str:
    cmd = cmd_template.replace("{prompt}", shlex.quote(prompt))
    try:
        proc = subprocess.run(cmd, shell=True, cwd=cwd, timeout=timeout,
                              capture_output=True, text=True)
        return (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"")
        if isinstance(out, bytes):
            out = out.decode(errors="replace")
        return out + f"\n[skill_gate] TIMEOUT after {timeout}s"


def is_meaningful(output: str) -> bool:
    """Ungueltig = keine inhaltliche Zeile (nur Leerraum/Harness-Warnungen in eckigen Klammern)."""
    for line in output.splitlines():
        s = line.strip()
        if s and not s.startswith("["):
            return True
    return False


def evaluate(results: dict, ctx_marker: str, skill_marker: str) -> dict:
    def r(pid):
        return results[pid]

    def ctx(pid):
        return ctx_marker in r(pid)["output"]

    def skl(pid):
        return skill_marker in r(pid)["output"]

    neutral = ["P1", "P2", "P3"]
    relevant = ["P4", "P5", "P6", "P7", "P8"]
    irrelevant = ["P9", "P10"]

    g1_hits = sum(ctx(p) for p in neutral)
    g2 = SKILL_NAME in r("D1")["output"]
    g3_valid = [p for p in relevant if r(p)["valid"]]
    g3_hits = sum(skl(p) for p in relevant)
    g4_violations = sum(skl(p) for p in irrelevant)
    g6 = skl("P4") == skl("P11")
    mech = skl("D2")
    invalid = [p for p, v in results.items() if not v["valid"]]

    verdicts = {
        "G1_context_file":    {"pass": g1_hits >= 2, "detail": f"{g1_hits}/3 neutrale Prompts mit Kontext-Marker"},
        "G2_discovery":       {"pass": g2, "detail": f"Skill-Name in D1 genannt: {g2}"},
        "G3_spontaneous":     {"pass": g3_hits >= 3,
                               "detail": f"{g3_hits}/5 relevante Prompts aktiviert "
                                         f"({len(g3_valid)}/5 gueltig; ungueltige zaehlen nicht als Nicht-Aktivierung)"},
        "G4_specificity":     {"pass": g4_violations == 0, "detail": f"{g4_violations}/2 Fehlaktivierungen"},
        "G6_repeatability":   {"pass": g6, "detail": f"P4={skl('P4')} vs P11={skl('P11')}"},
        "MECH_explicit_load": {"pass": mech, "detail": f"Skill-Marker bei expliziter Aufforderung (D2): {mech}"},
    }
    all_pass = all(v["pass"] for v in verdicts.values())
    mechanics_ok = all(verdicts[k]["pass"] for k in
                       ("G1_context_file", "G2_discovery", "G4_specificity", "MECH_explicit_load"))
    if all_pass:
        overall = "PASS"
    elif mechanics_ok and not verdicts["G3_spontaneous"]["pass"]:
        overall = "MECHANICS_OK_NO_SPONTANEOUS_ACTIVATION"  # der CC-x-GLM-Befund vom 16.08.
    else:
        overall = "FAIL"
    return {"verdicts": verdicts, "overall": overall, "invalid_runs": invalid}


def write_report(outdir: Path, label: str, args_ns, results: dict, ev: dict) -> None:
    lines = [f"# Skill-Gate Report — {label}", "",
             f"- harness-cmd: `{args_ns.harness_cmd}`",
             f"- Marker: Kontext=`{args_ns.context_marker}` · Skill=`{args_ns.skill_marker}`",
             f"- Workspace: `{args_ns.workspace}` · Timeout/Prompt: {args_ns.timeout}s", "",
             "| Prompt | Kategorie | gueltig | Kontext-Marker | Skill-Marker |",
             "|---|---|---|---|---|"]
    for pid, cat, _ in PROMPTS:
        v = results[pid]
        lines.append(f"| {pid} | {cat} | {'✓' if v['valid'] else '✗ (leer/No-Action)'} "
                     f"| {'✓' if args_ns.context_marker in v['output'] else '—'} "
                     f"| {'✓' if args_ns.skill_marker in v['output'] else '—'} |")
    lines += ["", "| Kriterium | Ergebnis | Detail |", "|---|---|---|"]
    for k, v in ev["verdicts"].items():
        lines.append(f"| {k} | {'✅ PASS' if v['pass'] else '❌ FAIL'} | {v['detail']} |")
    lines += ["", f"**Gesamturteil: {ev['overall']}**",
              f"\nUngueltige Laeufe (leer/No-Action): {', '.join(ev['invalid_runs']) or 'keine'}", ""]
    (outdir / "report.md").write_text("\n".join(lines))
    (outdir / "report.json").write_text(json.dumps({
        "label": label, "harness_cmd": args_ns.harness_cmd,
        "context_marker": args_ns.context_marker, "skill_marker": args_ns.skill_marker,
        "results": {pid: {"category": cat, "valid": results[pid]["valid"],
                          "context_marker": args_ns.context_marker in results[pid]["output"],
                          "skill_marker": args_ns.skill_marker in results[pid]["output"]}
                    for pid, cat, _ in PROMPTS},
        "evaluation": ev}, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser(description="Skill-Gate: Delivery-Experiment fuer eine Agent-Konfiguration")
    ap.add_argument("--harness-cmd", required=True,
                    help="Shell-Kommando mit {prompt}-Platzhalter, z. B. 'pi -p -a --provider X --model Y {prompt}'")
    ap.add_argument("--label", required=True, help="Name der Konfiguration (fuer Report/Ordner), z. B. pi-glm")
    ap.add_argument("--out", default="skill_gate_results", help="Ergebnis-Basisverzeichnis")
    ap.add_argument("--workspace", default="skill_gate_ws", help="Pfad des Marker-Test-Repos")
    ap.add_argument("--context-marker", default="ORAKEL", help="Codewort der Kontextdatei (statisch, Beschluss 21.08.)")
    ap.add_argument("--skill-marker", default="KOLIBRI", help="Codewort im Skill-Body (statisch, Beschluss 21.08.)")
    ap.add_argument("--timeout", type=int, default=300, help="Sekunden pro Prompt")
    ap.add_argument("--only", default=None, help="Nur diese Prompts (kommagetrennt, z. B. P4,P8,D1)")
    ap.add_argument("--skip-scaffold", action="store_true", help="Bestehenden Workspace weiterverwenden")
    args = ap.parse_args()

    ws = Path(args.workspace).expanduser().resolve()
    outdir = Path(args.out).expanduser().resolve() / args.label
    outdir.mkdir(parents=True, exist_ok=True)

    if not args.skip_scaffold:
        scaffold(ws, args.context_marker, args.skill_marker)
        print(f"[skill_gate] Workspace aufgebaut: {ws}")

    selected = None
    if args.only:
        selected = {p.strip() for p in args.only.split(",")}

    results = {}
    for pid, cat, prompt in PROMPTS:
        if selected and pid not in selected:
            results[pid] = {"output": "", "valid": False, "skipped": True}
            continue
        print(f"[skill_gate] {pid} ({cat}): {prompt}")
        out = run_prompt(args.harness_cmd, prompt, ws, args.timeout)
        (outdir / f"{pid}.log").write_text(out)
        results[pid] = {"output": out, "valid": is_meaningful(out)}

    ev = evaluate(results, args.context_marker, args.skill_marker)
    write_report(outdir, args.label, args, results, ev)
    print(f"\n[skill_gate] Report: {outdir}/report.md")
    for k, v in ev["verdicts"].items():
        print(f"  {k}: {'PASS' if v['pass'] else 'FAIL'} — {v['detail']}")
    print(f"[skill_gate] GESAMT: {ev['overall']}")
    return 0 if ev["overall"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
