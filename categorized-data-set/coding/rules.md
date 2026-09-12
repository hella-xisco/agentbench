# Coding guide

Every statement of a developer-written context file (`AGENTS.md` or `CLAUDE.md`)
is assigned to exactly one of four buckets. The buckets define the treatment
cells of the experiment: procedural statements form the K1 material, descriptive
statements the K2 material, normative and meta statements are excluded.

## Buckets and leading questions

| Bucket | Cells | Leading question |
|---|---|---|
| **P** procedural | K1, K1s | Can the agent act on it directly? Does it name an action, a command, a workflow, a tool choice? |
| **D** descriptive | K2, K2s | Does it state a fact about the repository (architecture, structure, purpose, location) without prescribing an action? |
| **N** normative | excluded | Would ignoring it plausibly leave the test result unchanged, because it concerns only form, style or process? |
| **M** meta | excluded | Does it talk about the file itself, its audience or its tooling ("This file provides guidance to ...")? It carries no repository knowledge. |

The overarching test behind P versus N is whether the statement plausibly
affects the test outcome or the solution path in the evaluation setting: build
commands, APIs, structural constraints, effective prohibitions and
effort-relevant exploration do; pure form, process and social content does not.

## Split rule for mixed statements

A statement that carries an obligation together with a concrete "how" is split
at the existing textual boundary: the command part becomes P, the obligation
part N. Example: "Use `Display.deprecated` with the version from
`lib/ansible/release.py` plus 3" is P (a concrete API); "deprecation cycle: 4
releases" is N.

## Wording status

No statement is rephrased. The `wording` column records what happened to the
source text when it was isolated as a statement.

| Value | Meaning |
|---|---|
| `verbatim` | sentence taken over unchanged |
| `split` | several statements separated from one source sentence or bullet; wording of the parts unchanged |
| `delisted` | taken out of a bullet list or code block; only list markers, comment signs or code fences removed |
| `grouped (n)` | n source lines kept together as one block (path trees, multi-step workflows); wording unchanged |
| `rephrased` | wording changed; target count zero, every such row would need a justification |

## Flags in the note column

`⚠grenz` marks a statement flagged as uncertain in the first pass, `⚠dup` a
statement the source repeats verbatim, `⚠tool` a statement that names a tool the
evaluation harness does not provide. Notes are in German; they document the
individual decisions and refer to the boundary rules below.

## Boundary rules

Twelve boundary questions were decided in the review of the first pass. Eight
were raised by statements flagged as uncertain in the first pass, four by
inconsistencies between statements of the same kind found during the review.
Every rule lists the statements it decided.

| Rule | Boundary question | Statements | Decision |
|---|---|---|---|
| G1 | Style rules that only a linter would check, and no linter runs in the evaluation (line length, trailing whitespace, import order, quote style). | ANS-59, ANS-60, ANS-65, GRA-31, GRA-32, PRA-22 | **N** confirmed. The two-gate evaluation (FAIL_TO_PASS, PASS_TO_PASS) is decisive; a style rule can never flip a gate. Distinct from G2: these never change program behaviour. |
| G2 | "Minimise the diff", "do not reformat globally": style in form, but with a plausible effect on the patch. | TRA-07, PRA-05, PRA-39 | **P**. A large reformat can genuinely break PASS_TO_PASS tests; the plausible outcome effect outweighs the stylistic form. |
| G3 | Prohibitions with a task effect: no hard-coding, no bare `except`, never edit generated files, no `@pytest.mark.asyncio`. | OPS-02, FMC-16, FMC-33, FMC-46 (and FMC-15) | **P** confirmed for all. |
| G4 | "Familiarise yourself with X": a frame for action without an executable step. | OPS-09 | **P**. A request for an exploration action (reading code) with an effort effect. |
| G5 | Instructions the agent cannot fulfil in an autonomous single run: "ask for confirmation", release and PR prohibitions. | PRA-38, ANS-11, FMC-27 | **N** confirmed. Context that points nowhere. |
| G6 | Instructions for using the product rather than developing the repository. | GRA-43 | **N**, flagged off-task in the note. |
| G7 | Facts that carry an obligation in the same sentence: fact in form, obligation in function. | ANS-08, FMC-30, PRA-26, PRA-31 | Split consistently: fact part **D**, obligation part **N**. ANS-08 is a pure fact and becomes D; PRA-31 is split into PRA-31 (D) and PRA-31b (N). |
| G8 | A repository (tinygrad) with no procedural statement at all. | TIN-* | Reported as empty and kept in the pool; its K1 and K1s cells run without a file or skill and are identical to the baseline. |
| G9 | Two statements about a task-list tool (TodoWrite) coded inconsistently as P and N. | ANS-04, ANS-56 | Both **N**: work organisation, test-blind, and the tool does not exist in the harness (G5 logic). |
| G10 | Preference pair: "prefer the standard library" versus "use existing code". | ANS-69, ANS-70 | ANS-69 stays **P** (a new dependency fails in the offline container), ANS-70 stays **N** (test-blind). |
| G11 | Tool or permission frames without an executable command: naming a tool, granting permission, consistency frames. | GRA-30, PRA-40, PRA-42, PRA-44 | All **N**. Without a command or API there is no P; PRA-03 stays P because it names a concrete mechanism. |
| G12 | A pitfall rule as the only procedural statement of a repository (wagtail). | WAG-08 | **P** confirmed. "You need to use X" is an action rule with direct code effect. |

## Second file versions

Two repositories ship their context file in two versions across the pool
tasks. The second version is coded against the first, so only the differing
lines receive a new decision.

- **fastmcp** `842e552a` versus `e7202ff0`: the later version drops one block
  ("Before creating a PR, evaluate whether documentation needs updating"), which
  is coded N and therefore excluded in both versions. The generated K1 and K2
  files are identical.
- **tinygrad** `b73aa6d4` versus `54541e66`: the second version rewords the
  same statements (two sentences merged, a renamed heading, a reformatted
  indentation rule) without adding or removing any. The bucket assignment is
  unchanged; the treatment files follow the wording of the version each task
  uses.
