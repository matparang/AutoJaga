# Model Fitting Analysis: x=[1,2,3,4,5], y=[2,4,8,16,32]

## Step 1: Observe the Data Pattern

| x | y  |
|---|----|
| 1 | 2  |
| 2 | 4  |
| 3 | 8  |
| 4 | 16 |
| 5 | 32 |

We see: y = 2^x exactly.
- 2ⁱ = 2
- 2² = 4
- 2³ = 8
- 2⁴ = 16
- 2⁵ = 32

→ This is a perfect exponential relationship.

## Step 2: Fit Linear Model y = mx + b

Using least-squares formulas:

Let n = 5
∑x = 1+2+3+4+5 = 15
∑y = 2+4+8+16+32 = 62
∑xy = (1)(2)+(2)(4)+(3)(8)+(4)(16)+(5)(32) = 2 + 8 + 24 + 64 + 160 = 258
∑x² = 1²+2²+3²+4²+5² = 1+4+9+16+25 = 55

Slope m = (n·∑xy − ∑x·∑y) / (n·∑x² − (∑x)²)
= (5·258 − 15·62) / (5·55 − 15²)
= (1290 − 930) / (275 − 225)
= 360 / 50 = **7.2**

Intercept b = (∑y − m·∑x)/n = (62 − 7.2·15)/5 = (62 − 108)/5 = (−46)/5 = **−9.2**

→ Linear model: **y = 7.2x − 9.2**

### Predictions & Residuals

| x | y_true | y_pred = 7.2x−9.2 | residual = y_true − y_pred |
|---|--------|---------------------|----------------------------|
| 1 | 2      | −2.0                | 4.0                        |
| 2 | 4      | 5.2                 | −1.2                      |
| 3 | 8      | 12.4                | −4.4                      |
| 4 | 16     | 19.6                | −3.6                      |
| 5 | 32     | 26.8                | 5.2                        |

✅ Verified: sum of residuals = 4.0 −1.2 −4.4 −3.6 + 5.2 = 0 (as expected for OLS).

### RMSE (Root Mean Squared Error)
Squared residuals: [16.00, 1.44, 19.36, 12.96, 27.04] → sum = **76.80**
Mean = 76.80 / 5 = 15.36
RMSE = √15.36 = **3.92**

### R² (Coefficient of Determination)
y_mean = 62/5 = 12.4
SS_res = 76.80
SS_tot = Σ(y_i − y_mean)² = (2−12.4)² + (4−12.4)² + (8−12.4)² + (16−12.4)² + (32−12.4)²
= (−10.4)² + (−8.4)² + (−4.4)² + (3.6)² + (19.6)²
= 108.16 + 70.56 + 19.36 + 12.96 + 384.16 = **595.20**
R² = 1 − (SS_res / SS_tot) = 1 − (76.80 / 595.20) = 1 − 0.1290 = **0.8710**

⚠️ Earlier manual calc used wrong ∑xy (220 instead of correct 258). Corrected above.

✅ Linear model: **RMSE = 3.92**, **R² = 0.871** — decent but not great; residuals show clear curvature.

## Step 3: Propose Better Model — Exponential

Given y = [2,4,8,16,32], compute log₂(y):
log₂(2)=1, log₂(4)=2, log₂(8)=3, log₂(16)=4, log₂(32)=5 → [1,2,3,4,5] = x

So log₂(y) = x → y = 2^x is *exact*.

### Validate predictions:
| x | y_true | y_pred = 2^x | residual |
|---|--------|--------------|----------|
| 1 | 2      | 2            | 0        |
| 2 | 4      | 4            | 0        |
| 3 | 8      | 8            | 0        |
| 4 | 16     | 16           | 0        |
| 5 | 32     | 32           | 0        |

→ All residuals = 0.

### Metrics:
- SS_res = 0 → RMSE = √(0/5) = **0.0**
- R² = 1 − (0 / 595.20) = **1.0**

✅ Perfect fit.

## Step 4: Why Exponential Was Chosen
- The ratio y[i+1]/y[i] = 2 for all i → constant multiplicative growth → exponential.
- log₂(y) is perfectly linear with slope 1 and intercept 0.
- Linear residuals alternate in sign and grow in magnitude (4.0, −1.2, −4.4, −3.6, 5.2), indicating systematic underfitting at extremes.

## Conclusion
- Linear model: **RMSE = 3.92**, **R² = 0.871** — acceptable but flawed.
- Exponential model y = 2^x: **RMSE = 0.0**, **R² = 1.0** — exact.
- Discovery relied on: (1) computing successive ratios, (2) testing log-transform linearity, (3) inspecting residual pattern.
