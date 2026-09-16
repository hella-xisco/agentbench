# Statistical audit: main-run-qwen

This report records computed audit results. It does not formulate or revise research-question conclusions.

## Raw audit

- Planned runs: 852
- Tasks: 71
- Measurement counts: {'measurable': 844, 'not_measurable': 8}
- Outcome categories: {'evaluation_error': 8, 'failed_patch': 100, 'solved': 564, 'timeout': 180}

## Complete 2+2 samples

| Contrast | Included | Excluded |
|---|---:|---:|
| K1-K0 | 68 | 3 |
| K2-K0 | 69 | 2 |
| K1s-K1 | 69 | 2 |
| K2s-K2 | 68 | 3 |
| K0d-K0 | 69 | 2 |
| K1-K0d | 68 | 3 |
| K2-K0d | 69 | 2 |

## Observed cell rates

| Cell | S/M | pass@1 |
|---|---:|---:|
| K0 | 92/141 | 0.652482 |
| K0d | 97/141 | 0.687943 |
| K1 | 89/140 | 0.635714 |
| K1s | 95/142 | 0.669014 |
| K2 | 95/141 | 0.673759 |
| K2s | 96/139 | 0.690647 |

## Paired pass@1 contrasts

| Contrast | Tasks | Effect | 95% t CI | p | Holm p |
|---|---:|---:|---:|---:|---:|
| K1-K0 | 68 | -0.014706 | [-0.098269, 0.068857] | 0.72649 | 0.739082 |
| K2-K0 | 69 | 0.021739 | [-0.026283, 0.069761] | 0.369541 | 0.739082 |
| K1s-K1 | 69 | 0.028986 | [-0.047770, 0.105741] | 0.453716 | 0.818809 |
| K2s-K2 | 68 | 0.022059 | [-0.030980, 0.075097] | 0.409404 | 0.818809 |
| K0d-K0 | 69 | 0.036232 | [-0.019496, 0.091960] | 0.198888 | 0.596665 |
| K1-K0d | 68 | -0.051471 | [-0.135475, 0.032534] | 0.225623 | 0.596665 |
| K2-K0d | 69 | -0.014493 | [-0.072651, 0.043665] | 0.620606 | 0.620606 |

## Mean effort per measurable attempt

The same complete task set is used as for each solve-rate contrast. Failed attempts and timeouts contribute effort. Intervals are paired task-bootstrap percentile intervals, not Holm decisions or effort hypothesis tests.

| Contrast | Tasks | Runs/cell | Unit | Mean a | Mean b | Difference | 95% bootstrap CI |
|---|---:|---:|---|---:|---:|---:|---:|
| K1-K0 | 68 | 136 | Tokens [×10³] | 1313.92 | 1262.58 | +51.34 | [-70.05, +157.38] |
| K1-K0 | 68 | 136 | Model API calls [calls] | 41.31 | 40.32 | +0.99 | [-1.60, +3.36] |
| K1-K0 | 68 | 136 | Run-time [s] | 830.99 | 781.69 | +49.31 | [+9.74, +88.33] |
| K2-K0 | 69 | 138 | Tokens [×10³] | 1207.45 | 1283.53 | -76.08 | [-165.35, +11.32] |
| K2-K0 | 69 | 138 | Model API calls [calls] | 39.20 | 41.05 | -1.85 | [-4.33, +0.67] |
| K2-K0 | 69 | 138 | Run-time [s] | 748.38 | 792.34 | -43.96 | [-77.97, -10.60] |
| K1s-K1 | 69 | 138 | Tokens [×10³] | 1089.52 | 1302.48 | -212.96 | [-322.16, -102.50] |
| K1s-K1 | 69 | 138 | Model API calls [calls] | 36.88 | 41.07 | -4.20 | [-6.84, -1.42] |
| K1s-K1 | 69 | 138 | Run-time [s] | 729.05 | 828.96 | -99.92 | [-141.67, -58.50] |
| K2s-K2 | 68 | 136 | Tokens [×10³] | 1128.57 | 1171.99 | -43.42 | [-132.28, +48.08] |
| K2s-K2 | 68 | 136 | Model API calls [calls] | 37.86 | 38.26 | -0.40 | [-2.65, +1.81] |
| K2s-K2 | 68 | 136 | Run-time [s] | 746.32 | 741.25 | +5.07 | [-31.86, +42.44] |
| K0d-K0 | 69 | 138 | Tokens [×10³] | 1281.64 | 1268.86 | +12.78 | [-114.67, +146.40] |
| K0d-K0 | 69 | 138 | Model API calls [calls] | 40.68 | 40.80 | -0.12 | [-2.72, +2.46] |
| K0d-K0 | 69 | 138 | Run-time [s] | 784.57 | 784.12 | +0.44 | [-36.44, +39.59] |
| K1-K0d | 68 | 136 | Tokens [×10³] | 1311.95 | 1270.76 | +41.19 | [-120.48, +179.70] |
| K1-K0d | 68 | 136 | Model API calls [calls] | 41.26 | 40.11 | +1.15 | [-1.71, +3.68] |
| K1-K0d | 68 | 136 | Run-time [s] | 831.54 | 781.93 | +49.61 | [+9.24, +88.23] |
| K2-K0d | 69 | 138 | Tokens [×10³] | 1204.59 | 1284.89 | -80.30 | [-195.80, +29.54] |
| K2-K0d | 69 | 138 | Model API calls [calls] | 39.14 | 40.55 | -1.41 | [-3.59, +0.88] |
| K2-K0d | 69 | 138 | Run-time [s] | 747.29 | 785.56 | -38.26 | [-77.51, +1.39] |
