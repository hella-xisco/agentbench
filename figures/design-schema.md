# Design-Schema für Thesis-Visuals — v2.3 (aktualisiert 16.09.2026)

Gilt für **alle** Schaubilder in Thesis + Präsentation. Änderungen nur bewusst + Versionsbump hier.
*Vorgänger v1 (09.08.2026) abgelöst: Farbrollen neu belegt (Artefakt als eigene Rolle, Aqua gestrichen), draw.io als Werkzeug ergänzt, Palette zentralisiert. Begründung im Decisions-Log 26.08.*

## Farbe kommt aus genau einer Datei

**Nie einen Hex-Wert von Hand in eine Figur tippen.** Alle Farben stehen in [`palette.json`](palette.json); draw.io kennt keine Farbvariablen, deshalb übernimmt ein Skript die Zentralisierung:

| Kommando | Wirkung |
|---|---|
| `python3 scripts/figures_palette.py --check` | meldet jede Farbe in einer Figur, die nicht in `palette.json` steht (Drift-Wächter) |
| `python3 scripts/figures_palette.py --sync` | erzeugt die VS-Code-Palette (`.vscode/settings.json`, zwischen Markern) + die Shape-Library `schema-v2.xml` |
| `python3 scripts/figures_palette.py --recolor` | färbt bestehende Figuren nach `migrations` um |

**Palette später ändern** = `palette.json` editieren → `--recolor` → `--sync` → `./build.sh`. Keine Figur wird dabei von Hand angefasst.

## Format & Pipeline

Zwei Quellsorten, beide in `figures/`:

- **`*.drawio`** — visuell editiert in VS Code (Extension `hediet.vscode-drawio`). Unkomprimiertes XML ⇒ lesbare git-Diffs. **Standard für alle neuen Figuren.**
- **`*.svg`** — handgeschrieben, `viewBox="0 0 960 540"` (16:9). Bestand aus Kap. 2; nicht in draw.io öffnen, der Editor strukturiert sie beim Speichern um.

- **Build:** `./build.sh` → `.svg` (für die Markdown-Drafts) + `.pdf` (LaTeX) + `@2x.png` (Folien)
- **Werkzeuge:** `brew install --cask drawio && brew install librsvg`
- **Ablage:** inhaltsbenannt, NICHT sektionsnummeriert (Nummern wandern)
- **Kein Titel und keine Legende im Bild** — beides liefert die LaTeX-Caption bzw. die Folie. Box-/Rahmen-Labels sind erlaubt, Direktlabels sind der Legende vorzuziehen.
- **Datenplots:** Achsen-/Panelbeschriftungen und ein erforderlicher Farb-/Symbolschlüssel dürfen in der Grafik stehen. Kein zusätzlicher allgemeiner Grafiktitel, der die Caption wiederholt. Fließtext beschreibt beobachtete Muster; Caption erklärt Messgröße, Nenner, Einheiten und Herkunft, ohne die Interpretation nochmals auszuschreiben.
- Hintergrund immer deckend weiß (`#ffffff`) — druck- und foliensicher, kein Dark Mode (Print-Medium).
- LaTeX: `\includegraphics[width=\textwidth]{<name>}`; `\graphicspath` muss dieses Verzeichnis enthalten.

## Farbrollen (feste Semantik über alle Figuren!)

| Rolle | Token | Farbe | Verwendung |
|---|---|---|---|
| **Harness / Untersuchungsgegenstand** | `harness` · `harness-fill` · `harness-dark` | `#5b83d6` · `#dde5f8` · `#2f5ba8` | Harness-Rahmen/-Box, alles was „unsere Schicht" ist; in Ablauf-Figuren die **Skripte** |
| **Fokus-Locus** | `focus` | `#2f5ba8` als 3-px-Kontur | genau EIN Element pro Figur (der Ort, an dem die Ablation angreift) — **Rollenfarbe bleibt**, betont wird über die Kontur; ist der Fokus selbst ein Harness-Element, wird er zusätzlich solide `#2f5ba8` mit weißer Schrift |
| **Artefakt / Daten** | `artifact` · `artifact-stroke` | `#f7d15c` · `#b8912c` | Task, Patch, Trajectory, Report, Context-File — alles, was Datei ist statt Handlung |
| **Environment** | `environment` · `environment-fill` | `#b0763f` (gestrichelt `7 5`) · `#e6e5e1` | Repo/FS/Shell/Container/Tests — alles außerhalb des Harness |
| **Modell / neutrale Struktur** | `model` · `model-stroke` | `#f0efec` · `#52514e` | Modell (in der Studie fixiert!), neutrale Boxen |
| Ink primär / sekundär / muted | `ink` · `ink-secondary` · `ink-muted` | `#0b0b0b` · `#52514e` · `#898781` | Titel / Fließlabels + Pfeile / Nebenlabels |
| Hairline / Rahmen neutral | `hairline` · `rule` | `#e1e0d9` · `#c3c2b7` | Banner, Trennlinien |
| Rampe hell / dunkel | `sequence-low` · `sequence-high` | `#5b83d6` · `#24406f` | nur Kurven-Schemata, s. Sonderregel unten |
| **Serie GLM / Serie Qwen** (v2.1, 03.09.) | `series-glm` · `series-glm-fill` · `series-qwen` · `series-qwen-fill` | `#2aa198` · `#d4efec` · `#8250df` · `#e6dcf8` | **nur Daten-Plots (Kap. 4):** Modell 1 türkis, Modell 2 lila (Beschluss Francisco 03.09.); als Paar CVD-validiert; nie in Schema-Figuren, dort gilt die Rollen-Semantik oben |
| **Run outcomes** (v2.2, 15.09.) | `outcome-solved` · `outcome-failed-patch` · `outcome-empty-patch` · `outcome-no-action` · `outcome-timeout` · `outcome-evaluation-error` | `#4f789b` · `#adc5d8` · `#d8d8d4` · `#e3bd65` · `#b98355` · `#b85c5c` | **nur Outcome-Kompositionen:** Farbe kodiert die Ergebniskategorie. Die Modellfarben sind hier verboten; Konfigurationen werden als getrennte, direkt beschriftete Blöcke gezeigt. |

**Regel:** Farbe folgt der Entität oder der ausdrücklich deklarierten Datenrolle, nie der Position. In Schema-Figuren heißt Blau „Harness/unser Subjekt", Gelb „Artefakt" und Orange „Environment". In Ergebnisfiguren gelten entweder die Modell-Serienfarben oder die Outcome-Farben, niemals beides für dieselbe Kodierung. Text trägt IMMER Ink-Farben (bzw. Weiß auf solidem Fokus-Blau), nie die Akzentfarbe als Fließtext.

**Phasenprofile (v2.3):** `phase-explore` = blau, `phase-edit` = gelb, `phase-validate` = braun, `phase-other` = grau. Die Phase hat in GLM und Qwen dieselbe Farbe. Konfigurationen werden durch getrennte, direkt beschriftete Blöcke identifiziert; Modell-Serienfarben dürfen nicht die Phase ersetzen. Der Farb-/Symbolschlüssel in den beiden Kontrast-Forest-Plots identifiziert hingegen die Konfiguration (GLM Kreis/türkis, Qwen Raute/lila), nicht Evidenz oder Ergebniskategorie.

*Änderung gegenüber v1: Artefakte mussten sich das Modell-Grau leihen — deshalb war in Ablauf-Figuren nicht unterscheidbar, was Datei und was Modell ist. Der Reserve-Akzent Aqua war in keiner Figur im Einsatz und ist gestrichen.*

## Zwei Figur-Typen, **eine** Farbsemantik

| | Konzept-Figuren (Kap. 2) | Ablauf-Figuren (Kap. 3) |
|---|---|---|
| zeigt | Entitäten und ihr Verhältnis | Schritte über Zeit und Ort |
| Harness-Blau | Harness bzw. seine Komponenten | die ausgeführten Skripte |
| Artefakt-Gelb | (selten) | Task, Patch, Trajectory, Report |
| Environment | gestrichelter Rahmen | Lane-Fläche + gestrichelte Grenze |

**Lanes tragen Orte, nicht Phasen** (Host-FS / Container) — die Phase steht als Achsenbeschriftung. Ort und Phase in derselben Achse zu mischen macht die Figur unlesbar.

## Typografie (bei 960er-Breite; druckt bei \textwidth ≈ 6–8 pt)

- Font-Stack: `"Helvetica Neue", Helvetica, Arial, sans-serif` (in draw.io: `Helvetica`)
- Box-Titel: **15–17 px bold**, Ink primär (bzw. weiß auf Fokus-Blau) — **keine Versalien**, ALL CAPS liest im Druck schlechter
- Box-Subzeile: 12–13 px, muted/sekundär
- Pfeil-/Mikro-Labels: 12–13 px, sekundär — nie unter 12 px
- Rahmen-Label (außen über Box): 20 px bold + 14 px muted Zusatz
- Annotationen (kursiv): 12–13 px italic, Fokus-Blau `#2f5ba8` wenn These-Bezug, sonst muted
- Sprache in Figuren: **Englisch** (Thesis-Sprache), auch in Lane- und Achsenlabels

## Formen & Pfeile

- Boxen: `rx="8"` (Banner/Pills) bis `rx="16"` (große Rahmen), Stroke 1.4–2 px — in draw.io `rounded=1;arcSize=12`
- Pfeile: 1.8–2 px, `#52514e`, Dreiecks-Marker; Doppelpfeil = Marker an beiden Enden
- Gestrichelt = „Grenze/Naht/extern": Environment-Kontur `7 5`, Provider-Naht `5 4`
- Abstände: 24-px-Rhythmus; nichts näher als 12 px an der Kante

## Figur-Zuständigkeiten

- **`harness-anatomy.svg`** (§2.3): *Anatomie* — öffnet die Box: E/T/C/S/L/V innen, Modell im Zentrum, Environment nur angedeutet. C = Fokus-Locus.
- **`model-harness-environment.svg`** (§2.5): *Topologie* — schließt die Box: drei Schichten, geschlossener Loop, Harness bewusst OHNE Innenleben, Provider-Naht gestrichelt (§2.4).
- **`run-pipeline.drawio`** (§3.2): *Apparatur* — was pro Lauf physisch passiert: zwei Container, der Agent-Patch als einzige Brücke, zwei Gates. Zeigt zugleich, an welcher Stelle die K-Zelle eingespeist wird. Terminologie seit 29.08.: Host-Bänder = „Orchestrator — host filesystem" (das Wort *harness* gehört allein dem Agenten-Gerüst; Beschluss s. decisions.linear.md), Agent-Kasten trägt die Unterzeile „harness × model".
- Präsentations-Erzählung: Zoom-out (Topologie) → Zoom-in (Anatomie) → Ablauf (Apparatur).

## Gebaute Figuren

### Aktiver Thesisbestand und Abgaberegister (16.09.2026)

Verbindlich für den aktuell eingebundenen Bestand ist `data/analysis/thesis-assets.json` im Benchmark-Abgaberepository. Das automatisch aus LaTeX, Aux-Dateien und PDF erzeugte Register enthält **alle Tabellen und Abbildungen**, eindeutige Labels, kurze/lange Captions, tatsächliche Auftretensnummern und Quell-/Assetprüfsummen. Die folgenden älteren Bau-/Ideenlisten sind kein Nachweis einer aktuellen Einbindung.

| Aktive Abbildung | Label | Quelle / Generator |
|---|---|---|
| `agent-system.tex` | `fig:agent-system` | konzeptionelle TikZ-Quelle |
| `run-pipeline` | `fig:run-pipeline` | `run-pipeline.drawio`, SVG/PDF |
| `calibration-screens` | `fig:calibration-screens` | `calibration-screens.drawio`, SVG/PDF |
| `vp-outcomes-glm` | `fig:vp-outcomes-glm` | `thesis-results-assets pilot-figures`, Pilot-v2-Rohstatus |
| `vp-outcomes-qwen` | `fig:vp-outcomes-qwen` | derselbe Generator, Qwen-Pilot-v2-Rohstatus |
| `main-outcome-composition` | `fig:main-outcome-composition` | `main-results`, beide Main-v3-Rohstatusdateien |
| `pass1-contrast-forest` | `fig:pass1-contrast-forest` | `main-results`, beide Main-v3-Kontrastdateien |
| `mean-effort-contrast-forest` | `fig:mean-effort-contrast-forest` | `main-results`, beide Main-v3-Aufwanddateien |
| `phase-profile-v2` | `fig:phase-profile` | `main-results`, Main-v3-Rohstatus und Trajektorien; v2 ist nur der Assetdateiname |
| `pairwise-disagreement` | `fig:pairwise-disagreement` | `main-results`, beide Main-v3-Disagreementdateien |

Einheiten an Achsen-/Panel-/Spaltenbeschriftungen stehen in **[]**; kein Tausender-`k`. Kurze Verzeichnistitel duplizieren nicht die vollständigen Captions. Ergebnisgrafiken stehen nahe der ersten Referenz und ihrer Einordnung; feste Platzierung ist für kompakte Ergebnisblöcke erlaubt. Harte Float-Barrieren dürfen keine künstlich leeren Folge-/Grafikseiten erzwingen. Große lesbare Pilotmatrizen oder Ergebnistabellen können eigene Seiten beanspruchen. Nummerierung folgt stets dem tatsächlichen PDF-Auftreten, nicht der Position einer Referenz im Fließtext.

### Historische Bauübersicht

| Datei | Quelle | Sektion | Zweck |
|---|---|---|---|
| `experiment-path.drawio` | draw.io (04.09.) | §4.1.1 | Forschungsweg: E1–E7 als Kette (Artefakt-Gelb = Lauf/Gate), darunter je Knoten das fixierte Designelement (Harness-Blau) |
| `activation-matrix.drawio` | draw.io (04.09.) | §4.1.4 | 2×2 Harness × Modell, Spontan-Aktivierung als Bruch; Fokus-Kontur = gewählte Konfiguration Pi×GLM, gestrichelt = CC×GLM ohne Aktivierung |
| `harness-anatomy.svg` | handgeschrieben | §2.3 | Anatomie: E/T/C/S/L/V, C = Fokus |
| `model-harness-environment.svg` | handgeschrieben | §2.5 | Topologie: Schichten + geschlossener Loop |
| `position-u-curve.svg` | handgeschrieben | §2.1 | U-Kurve + Context Rot (schematisch!) |
| `knowledge-routes.svg` | handgeschrieben | §2.1 | Drei Wissenswege: weights vs. context window |
| `run-pipeline.drawio` | draw.io | §3.2 | Lauf-Apparatur: Orchestrator-Bänder + zwei Container (generate/evaluate), Agent-Patch als einziges Bindeglied, Two-Gate-Evaluation B→A, Context-File = Fokus |
| `calibration-screens.drawio` | draw.io | §3.7 | Teilgrafik der Apparatur: Generate-Phase ausgegraut, zwei bekannte Patches (gold / leer) durch die identische Evaluate-Hälfte, je Zeile eine Regel (gold → beide Gates · leer → Gate A muss scheitern), Pool als Schnitt; Fokus = Substitutionspunkt (known patch replaces the agent patch) |

**Sonderregel Kurven-Schemata** (position-u-curve): stilisierte Kurven ohne echte Daten IMMER mit „(schematic)"-Label + Quellenverweis in der Caption; Serien-Unterscheidung über die sequenzielle Ein-Farb-Rampe `sequence-low` → `sequence-high` (hell→dunkel = Magnitude), Direktlabels am Linienende statt Legende.

## Herkunft in der Caption

- eigene Abbildung: `Own illustration.`
- an eine Quelle angelehnt: `Adapted from \cite{key}.` — und die §-Ref in `quellen.dynamic.md` Spalte „Verwendet in" nachziehen
- Vorlage aus einem externen Werkzeug (Miro-Template, fremde Icon-Bibliothek): in der Caption benennen, `Own illustration.` allein wäre dann unvollständig

## Geplante weitere Figuren (gleiche Rollen!) — Register, Stand 04.09.2026

> Alle registrierten Figuren (geplant, ✅ gebaut, 💡 Ideen) bleiben im Register; welche für die Abgabe gebaut werden, entscheidet Francisco später (04.09.). „AI-modified“-Kennzeichnung von Abbildungen: nach der Formatierungs-Mail (Zeitplan §Final-Formatierung), Ort: Captions + KI-Erklärung.

Dies ist der **zentrale Ort für geplante Figuren** (Beschluss 03.09.); `zeitplan.dynamic.md` verweist hierher. Sektionsnummern nach der Gliederung vom 02./03.09.; Datei-Namen inhaltsbenannt (s. o.).

| Datei (geplant) | Sektion | Zweck | Datenquelle | Typ |
|---|---|---|---|---|
| `agent-loop.drawio` | Kap. 2 §2.2 Coding Agents | der agentische Loop observe → think → act | — | Schema |
| `context-operations.drawio` | Kap. 2 §2.5 Context Engineering | die vier Kontext-Operationen (write/select/compress/isolate) | — | Schema |
| `upfront-vs-progressive-disclosure.drawio` | Kap. 2 §2.5.2 | K1 ↔ K1s: derselbe Inhalt als Upfront-Datei vs. Skill-Description + Body on demand | — | Schema |
| `passk-vs-passhoch-k.drawio` | Kap. 2 §2.7 Evaluating Stochastic Agents | pass@k vs. pass^k über k bei p = 0,7 | Formel | Kurven-Schema („(schematic)“) |
| `eth-critique-to-design.drawio` | Kap. 3 §3.1 | sechs Lücken → sechs Designelemente | — | Schema |
| `k-matrix.drawio` | Kap. 3 §3.4 Study Design | 2×2 Wissensart × Delivery Format + K0/K0d als Leiter | tab:cells | Schema |
| ✅ `experiment-path.drawio` (gebaut 04.09., eingebunden §4.1.1) | Kap. 3 §3.6.4 / Kap. 4 §4.1.1 | **Forschungsweg:** pre-study experiments E1–E7 als Kette, je Knoten die Entscheidung, die er fixiert hat (Fehlerkategorie · Variance Pilot · Base-Fail-Screen · Pi als Harness · System-Prompt-Ersatz · Qwen-Parameter · Proxy-Port) | `experiments/README.md` §Run-Register, Kap.-4-Kommentarblock 4.1.1 | Ablauf (Skripte = harness-Rolle, Läufe = Artefakt) |
| ✅ `activation-matrix.drawio` (gebaut 04.09., eingebunden §4.1.4 neben tab:activation-matrix) | Kap. 4 §4.1.4 | 2 Harnesses × 2 Modelle, Spontan-Aktivierung als Bruch je Zelle (Pi×GLM 3/3 · CC×GLM 0/5 · Pi×Sonnet 3/3 · CC×Sonnet 2/3) | `experiments/2026-08-16_02-machbarkeit-glm-skills/setup-log.md` | Matrix |
| ⛔ `results-two-bars` / `results-two-panel` | — | Beim Phase-B-Umbau entfernt, weil sie rohe Zellraten mit überholter Bootstrap-Unsicherheit kombinierten und die kontrastspezifische gepaarte Inferenz nicht abbildeten. | historische Ergebnisartefakte | nicht mehr einbinden |
| ⛔ `delivery-staircase` | — | Beim Phase-B-Umbau zugunsten der exakten Aktivierungstabelle entfernt. | historische Ergebnisartefakte | nicht mehr einbinden |
| ✅ `pass1-contrast-forest` | Kap. 4 RQ4 | Richtung, Größe und Unsicherheit aller sieben gepaarten pass@1-Kontraste, nach RQ gruppiert; keine Holm-Kodierung. Übersichtstabelle dokumentiert exakte Werte und Entscheidungen. GLM = Kreis, Qwen = Raute, jeweils feste Serienfarbe. | beide `statistics-v3/contrast_results.csv` | Forest |
| ✅ `mean-effort-contrast-forest` (16.09.) | Kap. 4 RQ4 | Drei Panels für Differenzen in mittlerem Aufwand pro messbarem Versuch: Tokens [×10³], model API calls [calls], run-time [s]. Eigene Skala je Ressource, sieben Kontraste nach RQ gruppiert, individuelle Bootstrapintervalle, Nulllinie. Marker/Farben wie pass@1; keine p-/Holm-/Signifikanzkodierung. | beide `statistics-v3/effort_bootstrap.json`; `thesis-results-assets main-results` | Drei-Panel-Forest |
| ⛔ `forest-effort` / `task-differences` / `bootstrap-distribution` | — | Historische Darstellungen der abgelösten Stufenlogik; die finale Auswertung berichtet gepaarte t-Inferenz für pass@1 und Bootstrapintervalle ausschließlich für Aufwand. | historische Ergebnisartefakte | nicht mehr einbinden |
| ❌ `noise-floor-derivation` (Daten-Plot, gebaut 03.09., eingebunden §4.1.5 am 04.09., **ausgebaut 10.09.**) | — | links 20 VP-Runden mit ±σ; rechts Skalierung σ → Schranke (÷√7,1, ÷√2, ×2) neben SE(Δ) nach Formel und empirisch — verworfen: 20 Balken kodierten eine Zahl, die rechte Treppe mischte Zell-σ, Schranke und Kontrast-SE auf einer Achse; Rechenweg steht als Formel in Kap. 3 §Noise Floor, Schranke-vs-KI im Forest-Plot. Dateien + Funktion bleiben (decisions 10.09.) | `experiments/2026-08-20_01-vp-stufe1` (analyze_vp) + JSON | Zwei-Panel |
| ✅ `vp-outcomes-glm` / `vp-outcomes-qwen` (am 15.09. aus den Phase-B-Ausgaben neu erzeugt) | Kap. 4 §4.1.5 | Outcome-Matrix mit Task $t$, Wiederholung $j$ und gelösten Wiederholungen je Task; Legende für solved, failed patch, timeout, empty patch und no action | `experiments/2026-08-20_01-vp-stufe1/analysis/variance-pilot-v2/raw_status_mapping.csv` bzw. `experiments/2026-08-22_02-vplight-qwen/analysis/variance-pilot-v2/raw_status_mapping.csv`; Generator: `scripts/analysis/src/thesis_analysis/pilot_figures.py` über `thesis-results-assets pilot-figures` | Matrix |
| ❌ `vp-convergence` (am 15.09. aus dem Thesis-Text entfernt) | Historisches Artefakt, nicht mehr eingebunden | Die frühere laufende Darstellung von Löserate und Streuung wird nicht als Entscheidungsgrundlage des Piloten verwendet. Pilotkennzahlen und die prospektive Dimensionierung stehen stattdessen in den reproduzierbaren Tabellen. | Historische Datei bleibt erhalten, ist aber kein finaler Ergebnisbestandteil. | Zwei-Panel-Linien |
| ✅ `pairwise-disagreement` (Phase-B-Neubau) | Kap. 4 §4.7 | Pairwise disagreement probability je Zelle und Konfiguration; nur Tasks mit zwei messbaren Wiederholungen | beide `statistics-v2/pairwise_disagreement.csv` | Dot plot |
| ⛔ `solve-efficiency-plane` (mit Phase-B-Umbau aus §4.2 entfernt) | — | Alte Darstellung mischte die überholte pass@1-Bootstrap-Unsicherheit mit Zellwerten und duplizierte die Übersichtstabelle. | historische Ergebnisartefakte | nicht mehr einbinden |
| ⛔ `sensitivity-forest` | — | Entfernt: delivered-only ist die einzige finale Sensitivitätsanalyse und wird als exakte Tabelle berichtet. | historische Ergebnisartefakte | nicht mehr einbinden |
| ✅ `main-outcome-composition` (Phase-B-Neubau, vereinfacht 16.09.) | Kap. 4 §4.2 | zwei Balken mit über alle sechs Zellen aggregierten Outcomes: 852 geplante Läufe je GLM-/Qwen-Konfiguration; solved, failed patch, empty patch, no-action, timeout, evaluation error; Farben kodieren ausschließlich Outcomes, kein interner Grafiktitel | beide `statistics-v2/raw_status_mapping.csv` | Gestapelte Balken |
| ✅ `phase-profile-v2` (Phase-B-Neubau) | Kap. 4 §4.7 | mittlere Tool Calls pro messbarem handelndem Lauf, gestapelt nach explore/edit/validate/other, beide Konfigurationen | beide `statistics-v2/raw_status_mapping.csv` und verlinkte Trajektorien | Gestapelt |
| 💡 `no-action-task-map` (Idee 03.09., nicht gebaut) | Kap. 4 §4.8 (b) | Heatmap Task × Zelle (GLM): No-Action-Läufe 0/1/2 je Feld, Tasks nach Repo gruppiert — Task-Konzentration und „neue Nicht-Handlung“ in K0d/K1/K2 sichtbar | Trajektorien (Kategorie je Lauf; Export aus analyze_hauptrun ergänzen) | Heatmap (sequenziell) |
| 💡 `repo-effects-heatmap` (Idee 03.09., nicht gebaut) | Kap. 4 §4.7 (5) | Repo × 7 Kontraste, divergierende Farbe um 0, beide Modelle als zwei Panels; Felder mit n < 5 ausgegraut — die Konzentration des K0d-Schadens auf ansible/transformers/pr-agent | `exploratory.by_repo` (tab:repo-effects) | Heatmap (divergierend) |
| 💡 `cost-success-curve` (Idee 03.09., nicht gebaut) | Kap. 4 §4.2 / Kap. 5 | Anteil der Läufe, die gelöst haben UND unter Token-Budget B blieben, über B (log) je Zelle — parameterfreie zweite Ansicht der Solve Efficiency (auswertung §1c „Zweite Ansicht“); rechts läuft jede Kurve in pass@1 aus | Tokens + resolved je Lauf (Export ergänzen) | Kurvenschar (eine Zelle = eine Linie, K0 als Fokus) |
| 💡 `effort-distribution` (Idee 03.09., nicht gebaut) | Kap. 4 §4.2 / §4.8 (e) | Tokens je Lauf als Strip oder ECDF je Zelle auf log-Achse, Loop-Läufe markiert (GLM 12); zweites Panel Qwen Wall-Zeit-ECDF mit 1 320-s-Cap — die Zensur als Sprung sichtbar | Tokens/Wall je Lauf (Export ergänzen) | Strip/ECDF |
| 💡 `activation-outcome` (Idee 03.09., nicht gebaut) | Kap. 4 §4.4 | je Skill-Zelle und Modell zwei gestapelte Balken: Outcome der aktivierten vs. nicht aktivierten Läufe (solved · attempted · read-and-quit · übrige) — Selbstselektion und read-and-quit (GLM 23/44) in einem Bild | `skills` + Kategorie je Lauf (Export ergänzen) | Gestapelt |
| 💡 `exploratory-forest` (Idee 03.09., nicht gebaut) | Kap. 4 §4.7 | 8 Zellpaare + 4 Pools mit Bootstrap-KI, beide Modelle, wie forest-contrasts — „exploratory“ im Titel der Caption | `exploratory.pairs/pooled` (Stufe-2-Felder vorhanden) | Forest |
| 💡 `power-curve` (Idee 03.09., nicht gebaut) | Kap. 4 §4.1.5 / Kap. 3 §3.8 | Power gegen Δ (0–20 pp) für n′=71 × r=1/2/3 und n′=50 × r=3 nach der SE(Δ)-Formel; Markierung 10 pp/71 %, 15 pp/96 %, 5 pp/80 % ⇒ ≈4 300 Läufe — die Dimensionierung als Kurve | Formel Kap. 3 (d = 0,23), keine Messdaten | Kurven („(model)“-Label wie „(schematic)“) |

**Finale Daten-Plots in Kapitel 4** entstehen über `thesis-results-assets` im gesperrten Projekt `scripts/analysis/` aus den versionierten Phase-B-Ausgaben und den darin verlinkten Trajektorien. Der Generator schreibt SVG und rendert mit `rsvg-convert` nach PDF und PNG. Die historischen Skripte und Grafiken bleiben als Archiv erhalten, sind aber keine finale Ergebnisquelle. Farben stammen weiterhin ausschließlich aus `palette.json`: Modellvergleichsplots verwenden GLM = `series-glm` und Qwen = `series-qwen`; Outcome-Kompositionen verwenden stattdessen die sechs `outcome-*`-Rollen. Serien und Kategorien sind zusätzlich direkt beschriftet oder durch eine Legende identifiziert.

## Arbeitsablauf

**Einmalig einrichten**

```bash
brew install --cask drawio && brew install librsvg
code --install-extension hediet.vscode-drawio
```

Die Palette lädt VS Code aus `.vscode/settings.json` (Block zwischen den `figures-palette`-Markern) — nach dem Extension-Install einmal VS Code neu laden.

**Bestehende Figur ändern:** `run-pipeline.drawio` doppelklicken → visueller Editor. Farben nie aus dem freien Farbwähler nehmen, sondern aus **Style** (oben im Format-Panel, die fünf Rollen-Schemata) oder der Shape-Library **Thesis-Schema v2** in der linken Leiste. Im Farbdialog stehen die Palettenfarben oben und zeigen ihren Rollennamen als Tooltip.

**Neue Figur anlegen:** leere Datei `<inhalt>.drawio` erstellen → Shapes aus der Library ziehen → Regeln oben beachten (genau ein Fokus-Locus, kein Titel/keine Legende im Bild, englische Labels).

**Bauen und einbinden**

```bash
python3 scripts/figures_palette.py --check   # Fremdfarben?
./figures/build.sh            # -> .svg .pdf @2x.png
```

```latex
\begin{figure}[htbp]
  \centering
  \includegraphics[width=\textwidth]{run-pipeline}
  \caption[Measurement pipeline]{One run of the measurement pipeline. Own illustration.}
  \label{fig:run-pipeline}
\end{figure}
```

**Palette später ändern:** `palette.json` editieren → `--recolor` (nur bei Hex-Wechsel: vorher den alten→neuen Wert unter `migrations` eintragen) → `--sync` → `build.sh`. Keine Figur wird dabei von Hand angefasst.

**Fallstricke**

- `simpleLabels: true` ist gesetzt und muss gesetzt bleiben — sonst schreibt draw.io Text als ForeignObject, das `rsvg-convert` nicht rendert (Text wäre im PDF weg).
- Die vier handgeschriebenen SVGs **nicht** in draw.io öffnen und speichern — der Editor strukturiert sie um.
- `build.sh` überschreibt `<name>.svg`, wenn `<name>.drawio` existiert. Nie beide mit demselben Basisnamen anlegen.
