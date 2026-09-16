# Statistical audit: main-run-glm

This report records computed audit results. It does not formulate or revise research-question conclusions.

## Raw audit

- Planned runs: 852
- Tasks: 71
- Measurement counts: {'measurable': 834, 'not_measurable': 18}
- Outcome categories: {'empty_patch': 127, 'evaluation_error': 18, 'failed_patch': 197, 'no_action': 107, 'solved': 372, 'timeout': 31}

## Complete 2+2 samples

| Contrast | Included | Excluded |
|---|---:|---:|
| K1-K0 | 68 | 3 |
| K2-K0 | 69 | 2 |
| K1s-K1 | 67 | 4 |
| K2s-K2 | 70 | 1 |
| K0d-K0 | 69 | 2 |
| K1-K0d | 68 | 3 |
| K2-K0d | 69 | 2 |

## Observed cell rates

| Cell | S/M | pass@1 |
|---|---:|---:|
| K0 | 63/139 | 0.453237 |
| K0d | 52/139 | 0.374101 |
| K1 | 55/138 | 0.398551 |
| K1s | 72/137 | 0.525547 |
| K2 | 59/140 | 0.421429 |
| K2s | 71/141 | 0.503546 |

## Paired pass@1 contrasts

| Contrast | Tasks | Effect | 95% t CI | p | Holm p |
|---|---:|---:|---:|---:|---:|
| K1-K0 | 68 | -0.058824 | [-0.166524, 0.048877] | 0.279544 | 0.559087 |
| K2-K0 | 69 | -0.036232 | [-0.151512, 0.079048] | 0.532651 | 0.559087 |
| K1s-K1 | 67 | 0.134328 | [0.026947, 0.241709] | 0.0150044 | 0.0300088 |
| K2s-K2 | 70 | 0.078571 | [-0.039147, 0.196289] | 0.187395 | 0.187395 |
| K0d-K0 | 69 | -0.079710 | [-0.206061, 0.046641] | 0.212383 | 0.637149 |
| K1-K0d | 68 | 0.014706 | [-0.095882, 0.125293] | 0.791495 | 0.800169 |
| K2-K0d | 69 | 0.043478 | [-0.058979, 0.145936] | 0.400084 | 0.800169 |

## Mean effort per measurable attempt

The same complete task set is used as for each solve-rate contrast. Failed attempts and timeouts contribute effort. Intervals are paired task-bootstrap percentile intervals, not Holm decisions or effort hypothesis tests.

| Contrast | Tasks | Runs/cell | Unit | Mean a | Mean b | Difference | 95% bootstrap CI |
|---|---:|---:|---|---:|---:|---:|---:|
| K1-K0 | 68 | 136 | Tokens [×10³] | 1053.81 | 732.92 | +320.89 | [-26.39, +692.22] |
| K1-K0 | 68 | 136 | Model API calls [calls] | 32.13 | 26.14 | +5.99 | [-1.93, +14.79] |
| K1-K0 | 68 | 136 | Run-time [s] | 279.15 | 229.64 | +49.50 | [+12.58, +87.74] |
| K2-K0 | 69 | 138 | Tokens [×10³] | 860.61 | 735.40 | +125.21 | [-130.65, +438.77] |
| K2-K0 | 69 | 138 | Model API calls [calls] | 28.55 | 26.22 | +2.33 | [-4.28, +10.09] |
| K2-K0 | 69 | 138 | Run-time [s] | 240.55 | 229.12 | +11.43 | [-17.28, +41.90] |
| K1s-K1 | 67 | 134 | Tokens [×10³] | 1113.50 | 1060.19 | +53.31 | [-376.51, +480.75] |
| K1s-K1 | 67 | 134 | Model API calls [calls] | 35.31 | 32.21 | +3.10 | [-7.02, +12.54] |
| K1s-K1 | 67 | 134 | Run-time [s] | 256.95 | 278.88 | -21.93 | [-63.95, +22.65] |
| K2s-K2 | 70 | 140 | Tokens [×10³] | 818.38 | 850.23 | -31.85 | [-351.78, +274.45] |
| K2s-K2 | 70 | 140 | Model API calls [calls] | 30.63 | 28.30 | +2.33 | [-5.91, +10.57] |
| K2s-K2 | 70 | 140 | Run-time [s] | 247.38 | 239.17 | +8.21 | [-28.91, +46.47] |
| K0d-K0 | 69 | 138 | Tokens [×10³] | 571.65 | 735.40 | -163.75 | [-411.67, +65.37] |
| K0d-K0 | 69 | 138 | Model API calls [calls] | 21.09 | 26.22 | -5.14 | [-11.83, +1.64] |
| K0d-K0 | 69 | 138 | Run-time [s] | 214.98 | 229.12 | -14.13 | [-50.10, +20.57] |
| K1-K0d | 68 | 136 | Tokens [×10³] | 1053.81 | 575.66 | +478.15 | [+85.54, +923.19] |
| K1-K0d | 68 | 136 | Model API calls [calls] | 32.13 | 21.08 | +11.05 | [+1.88, +21.49] |
| K1-K0d | 68 | 136 | Run-time [s] | 279.15 | 215.92 | +63.23 | [+24.47, +104.24] |
| K2-K0d | 69 | 138 | Tokens [×10³] | 860.61 | 571.65 | +288.96 | [+49.95, +566.68] |
| K2-K0d | 69 | 138 | Model API calls [calls] | 28.55 | 21.09 | +7.46 | [+1.64, +13.85] |
| K2-K0d | 69 | 138 | Run-time [s] | 240.55 | 214.98 | +25.56 | [-5.45, +56.73] |
