# Changes between the first pass and the reviewed coding

Statements shared by both codings: 349. Bucket changed in the review: 9. Statements split in the review (new identifiers, no counterpart in the first pass): 3.

## Bucket changes

| id | first pass | reviewed | note |
|---|---|---|---|
| ANS-04 | P | N | ⚠tool (Pi hat kein TodoWrite) · Entscheid 20.08. (G9): Arbeitsorganisation, testblind → N (Paar mit ANS-56) |
| ANS-08 | N | D | ⚠grenz entschieden 20.08. (G7): reiner Lizenz-Fakt → D |
| OPS-09 | D | P | ⚠grenz entschieden 20.08. (G4): Erkundungs-Aufforderung mit Aufwands-Wirkung → P |
| TRA-07 | N | P | ⚠grenz entschieden 20.08. (G2): Diff-Minimierung hat plausible Patch-Wirkung → P (Trio mit PRA-05/39) |
| PRA-05 | N | P | ⚠grenz entschieden 20.08. (G2): Reformat-Verbot hat plausible Patch-Wirkung → P (Trio mit TRA-07/PRA-39) |
| PRA-39 | N | P | ⚠dup-nah zu PRA-05 · G2-Entscheid 20.08. → P |
| PRA-40 | P | N | ⚠grenz entschieden 20.08. (G11): Erlaubnis-Rahmen ohne Kommando, „coordinate" unerfüllbar → N |
| PRA-42 | P | N | ⚠grenz entschieden 20.08. (G11): Rahmen-Regel ohne ausführbares Kommando → N |
| PRA-44 | P | N | ⚠dup-nah zu PRA-03 · G11-Entscheid 20.08.: Rahmen-Regel → N (PRA-03 bleibt P: konkreter Mechanismus) |

## Split statements

| id | bucket | statement |
|---|---|---|
| PRA-26b | D | Configuration files in `pr_agent/settings/` are TOML |
| PRA-31b | N | run them only when credentials and sandboxes are configured |
| FMC-30b | D | Python ≥ 3.10 |
