# Categorized context-file dataset

Developer-written context files (`AGENTS.md`, `CLAUDE.md`) of the task pool,
decomposed into individual statements, each assigned to one of four knowledge
buckets, and recomposed into the treatment files of the experiment. This
directory is the data companion of the bachelor's thesis on repository knowledge
for coding agents; the thesis describes the design, the coding guide and the
results.

## Contents

```
categorized-data-set/
  coding/
    rules.md            coding guide: buckets, leading questions, split rule, boundary rules G1–G12
    statements.csv      352 statements: id, repository, source file, bucket, wording status, statement, note
    first-pass.csv      bucket of every statement in the frozen first pass (349 ids)
    changes.md          the 9 bucket changes and 3 splits made in the review
  source/
    <owner>__<repo>__<sha8>.md   the original context files, byte-identical to the pool
    provenance.json     per file: repository, file name, sha256, task instances, base and source commits
  treatment/<repo>/
    AGENTS.k1.md        procedural extract (K1 cell), empty when the repository has no procedural statement
    AGENTS.k2.md        descriptive extract (K2 cell)
    SKILL.k1s.md        the same extract wrapped as a skill (K1s cell); absent when the extract is empty
    SKILL.k2s.md        the same for K2s
    line-map.tsv        frozen assignment of every source line to a bucket and statement id
    line-review.txt     the source file annotated line by line with its bucket
  treatment/size-audit.md   character and token sizes of every extract, output of the five integrity checks
  scripts/count_m1c.py      bucket counts per repository and the list of changes between two codings
```

## Buckets

| Bucket | Cells | Content |
|---|---|---|
| P procedural | K1, K1s | commands, workflows, tool choices: how work is done here |
| D descriptive | K2, K2s | architecture, structure, domain facts: what the repository is |
| N normative | excluded | style rules, prohibitions without task effect, "should" statements |
| M meta | excluded | statements about the file itself, its audience or its tooling |

The leading questions, the split rule for mixed statements and the twelve
boundary rules are given in `coding/rules.md`.

## Procedure

1. Every source file was decomposed into statements at existing textual
   boundaries (sentences, bullets, code-block lines). The source wording is
   preserved in every statement; the `wording` column records whether a
   statement was taken verbatim, delisted, grouped or split.
2. A language model applied the coding guide to every statement and flagged
   the cases it considered uncertain. This assignment was frozen as the first
   pass (`coding/first-pass.csv`).
3. The author reviewed every statement, decided twelve boundary questions and
   recorded each decision as a rule (`coding/rules.md`). The review changed the
   bucket of 9 of the 349 shared statements and split 3 further statements;
   `coding/changes.md` lists them with their rule.
4. The treatment files were generated from the reviewed coding by a static line
   map per source file (`treatment/<repo>/line-map.tsv`), never by dynamic
   matching. Five mechanical checks (coverage, drift, verbatim fidelity, split
   consistency, statement coverage) guard the recomposition; their sizes are
   listed in `treatment/size-audit.md`. Skills use a fixed YAML header with a
   repository-specific name and a neutral description; the body is identical to
   the corresponding extract.

Only the twelve file versions of the ten repositories in the final task pool
were coded. `source/` also contains the context files of repositories that were
screened out before treatment construction (`coded: false` in
`provenance.json`); they are kept for completeness of the pool provenance.

## Reproducing the counts

```
cd scripts
python3 count_m1c.py ../coding/statements.csv --kappa ../coding/first-pass.csv
```

prints the bucket distribution per repository (134 P, 97 D, 107 N, 14 M) and
the nine statements whose bucket changed between the first pass and the review.

## Provenance and licences

The source files are the context files shipped by the repositories of the task
pool, taken either at the base commit of a task (`at_base_sha`) or from a later
commit when the file did not yet exist at the base commit (`future_commit`), as
recorded per instance in `source/provenance.json`. They are redistributed here
unchanged and only for the purpose of documenting the experiment. Each file
remains under the licence of its repository at the source commit:

| Repository | Licence at source commit |
|---|---|
| ansible/ansible | GPL-3.0 |
| getzep/graphiti | Apache-2.0 |
| huggingface/smolagents | Apache-2.0 |
| huggingface/transformers | Apache-2.0 |
| jlowin/fastmcp | Apache-2.0 |
| openai/openai-agents-python | MIT |
| OpShin/opshin | MIT |
| pdm-project/pdm | MIT |
| qodo-ai/pr-agent | AGPL-3.0 |
| tinygrad/tinygrad | MIT |
| vibrantlabsai/ragas | Apache-2.0 |
| wagtail/wagtail | BSD-3-Clause |

The treatment files are derived works of these files and carry the same
licences. The coding tables, the rules and the script are provided under the
licence of this repository.
