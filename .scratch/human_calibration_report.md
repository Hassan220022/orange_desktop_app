# Human BDT Calibration Report

Sites analyzed: **82** (74 accepted, 8 rejected)

## Proposed thresholds

```json
{
  "string_ampere_pos_accept_a": 4.4,
  "string_ampere_pos_revise_a": 5.0,
  "string_ampere_a": 3.0,
  "string_imbalance_reject_ratio": 0.85,
  "string_imbalance_revise_ratio": 0.7,
  "discharge_current_accept_a": 21.4,
  "discharge_slope_accept_a_per_min": 0.46,
  "discharge_slope_reject_a_per_min": 0.2,
  "discharge_spike_reject_a": 10.0,
  "incomplete_reject_minutes": 30.0,
  "incomplete_revise_minutes": 90.0,
  "overall_ignore_na_rules": [
    "R11",
    "R5",
    "R7"
  ]
}
```

## Deep-dive cases

### 0161CA — string imbalance (human Rejected, amp not matched)
- **0161CA** (Rejected): R3+=9.20A, imbalance=0.99, R9 Δ=4.80A, slope=-0.09 A/min, discharge=64.00 min — Batteries Amp not matched with the rectifier summation Amp

### 0307RE vs 3565CA — same R3 Δ≈0.9A at 10 min, different slope
- **0307RE** (Rejected): R3+=3.00A, imbalance=0.55, R9 Δ=40.20A, slope=0.33 A/min, discharge=133.00 min — Batteries Amp  fluctuating
- **3565CA** (Accepted): R3+=4.40A, imbalance=0.00, R9 Δ=5.30A, slope=0.04 A/min, discharge=137.00 min — no reason

## Human-rejected sites

| Site | Reason | Severity | R3+ | R3- | Imbalance | R9 Δ | Slope | Discharge min |
|------|--------|----------|-----|-----|-----------|------|-------|---------------|
| 0161CA | Batteries Amp not matched with the rectifier summation Amp | Mild | 9.20 | 0.00 | 0.99 | 4.80 | -0.09 | 64.00 |
| 0307RE | Batteries Amp  fluctuating | Mild | 3.00 | 0.00 | 0.55 | 40.20 | 0.33 | 133.00 |
| 4476UP | Batteries Amp  fluctuating | Mild | 2.60 | 1.80 | 0.53 | 6.20 | 0.06 | 112.00 |
| 0218UP | Incomplete test | Severe | — | — | — | — | — | — |
| 0218UP | Incomplete test | Severe | — | — | — | — | — | — |
| 0746CA | Rectefier  amp  fluctuating | — | 67.20 | 4.60 | 0.53 | 1.70 | 0.01 | 180.00 |
| 3765CA | Batteries Amp not matched with the rectifier summation Amp | Severe | 11.40 | 5.60 | 0.70 | 0.50 | 0.03 | 30.00 |
| 3907CA | Batteries Amp not matched with the rectifier summation Amp | Severe | 15.79 | 0.00 | 0.54 | 2.80 | -0.14 | 30.00 |

## Overlap analysis (accepted vs rejected)

```json
{
  "accepted_r3_pos_max": {
    "count": 14,
    "min": 0.0,
    "max": 4.399999999999999
  },
  "rejected_r3_pos_min": {
    "count": 6,
    "min": 2.6000000000000085,
    "max": 67.2
  },
  "accepted_slope_max": {
    "count": 14,
    "min": -0.04631578947368419,
    "max": 0.4599999999999994
  },
  "rejected_slope_min": {
    "count": 3,
    "min": 0.010000000000000018,
    "max": 0.32682926829268283
  },
  "accepted_imbalance_max": {
    "count": 14,
    "min": 0.0,
    "max": 0.6071428571428571
  },
  "rejected_imbalance_min": {
    "count": 6,
    "min": 0.531317494600432,
    "max": 0.992633517495396
  }
}
```

## All rows

| Site | Date | Human | R3+ | Slope | Imb | Disch min | Auto | BDT |
|------|------|-------|-----|-------|-----|-----------|------|-----|
| 3997CA | 2026-05-02 | Accepted | — | — | — | — | Rejected | OK |
| 0161CA | 2026-05-03 | Rejected | 9.20 | -0.09 | 0.99 | 64.00 | Rejected | OK |
| 0307RE | 2026-05-03 | Rejected | 3.00 | 0.33 | 0.55 | 133.00 | Rejected | OK |
| 0358SI | 2026-05-03 | Accepted | — | — | — | — | Rejected | OK |
| 0219UP | 2026-05-03 | Accepted | — | — | — | — | Rejected | OK |
| 0292UP | 2026-05-03 | Accepted | — | — | — | — | Rejected | OK |
| 0635UP | 2026-05-03 | Accepted | — | — | — | — | Rejected | OK |
| 0251UP | 2026-05-04 | Accepted | — | — | — | — | Rejected | OK |
| 3565CA | 2026-05-05 | Accepted | 4.40 | 0.04 | 0.00 | 137.00 | Rejected | OK |
| 4476UP | 2026-05-05 | Rejected | 2.60 | 0.06 | 0.53 | 112.00 | Rejected | OK |
| 0086UP | 2026-05-05 | Accepted | — | — | — | — | Rejected | OK |
| 0197CA | 2026-05-06 | Accepted | — | — | — | 12.00 | Rejected | OK |
| 1123CA | 2026-05-06 | Accepted | — | — | — | — | Rejected | OK |
| 3136UP | 2026-05-06 | Accepted | — | — | — | — | Rejected | OK |
| 0634UP | 2026-05-06 | Accepted | — | — | — | — | Rejected | OK |
| 0921UP | 2026-05-06 | Accepted | 0.30 | 0.17 | 0.61 | 63.00 | Rejected | OK |
| 3421CA | 2026-05-07 | Accepted | — | — | — | — | Rejected | OK |
| 0068AL | 2026-05-08 | Accepted | — | — | — | — | Rejected | OK |
| 4355CA | 2026-05-10 | Accepted | 0.00 | 0.19 | 0.54 | 37.00 | Rejected | OK |
| 4000CA | 2026-05-10 | Accepted | — | — | — | — | Rejected | OK |
| 3405CA | 2026-05-10 | Accepted | — | — | — | — | Rejected | OK |
| 0233CA | 2026-05-11 | Accepted | 0.00 | 0.09 | 0.00 | 85.00 | Rejected | OK |
| 0137DE | 2026-05-11 | Accepted | — | — | — | — | Rejected | OK |
| 0201UP | 2026-05-11 | Accepted | — | — | — | — | Rejected | OK |
| 3137UP | 2026-05-11 | Accepted | — | — | — | — | Rejected | OK |
| 0394CA | 2026-05-12 | Accepted | 0.60 | 0.33 | 0.36 | 20.00 | Rejected | OK |
| 0470RE | 2026-05-12 | Accepted | — | — | — | — | Rejected | OK |
| 3354UP | 2026-05-12 | Accepted | — | — | — | — | Rejected | OK |
| 0381UP | 2026-05-12 | Accepted | — | — | — | — | Rejected | OK |
| 3379CA | 2026-05-13 | Accepted | — | — | — | — | Rejected | OK |
| 1000CA | 2026-05-13 | Accepted | — | — | — | — | Rejected | OK |
| 4237CA | 2026-05-13 | Accepted | — | — | — | — | Rejected | OK |
| 3254CA | 2026-05-13 | Accepted | — | — | — | — | Rejected | OK |
| 0334SI | 2026-05-13 | Accepted | 1.70 | 0.25 | 0.51 | 67.00 | Rejected | OK |
| 0473SI | 2026-05-13 | Accepted | — | — | — | — | Rejected | OK |
| 3431UP | 2026-05-13 | Accepted | — | — | — | — | Rejected | OK |
| 0218UP | 2026-05-13 | Rejected | — | — | — | — | Rejected | OK |
| 0218UP | 2026-05-13 | Rejected | — | — | — | — | Rejected | OK |
| 4164UP | 2026-05-14 | Accepted | — | — | — | — | Rejected | OK |
| 0592UP | 2026-05-14 | Accepted | 3.60 | -0.05 | 0.00 | 105.00 | Rejected | OK |
| 0392SI | 2026-05-15 | Accepted | — | — | — | — | Rejected | OK |
| 0746CA | 2026-05-16 | Rejected | 67.20 | 0.01 | 0.53 | 180.00 | — | OK |
| 0034RE | 2026-05-16 | Accepted | — | — | — | — | Rejected | OK |
| 3724CA | 2026-05-17 | Accepted | — | — | — | — | Revise | OK |
| 2015UP | 2026-05-17 | Accepted | — | — | — | — | — | OK |
| 2015UP | 2026-05-17 | Accepted | — | — | — | — | — | OK |
| 3765CA | 2026-05-17 | Rejected | 11.40 | 0.03 | 0.70 | 30.00 | — | OK |
| 4324CA | 2026-05-17 | Accepted | 1.10 | 0.26 | 0.50 | 17.00 | Rejected | OK |
| 0455UP | 2026-05-17 | Accepted | 0.00 | 0.35 | 0.53 | 23.00 | Rejected | OK |
| 3362CA | 2026-05-18 | Accepted | — | — | — | — | — | OK |
| 2466CA | 2026-05-18 | Accepted | — | — | — | — | Rejected | OK |
| 3106CA | 2026-05-18 | Accepted | — | — | — | — | — | OK |
| 3580UP | 2026-05-18 | Accepted | 1.50 | 0.14 | 0.55 | 87.00 | Rejected | OK |
| 3975UP | 2026-05-18 | Accepted | — | — | — | — | Rejected | OK |
| 3124UP | 2026-05-18 | Accepted | — | — | — | — | Rejected | OK |
| 4166UP | 2026-05-18 | Accepted | — | — | — | — | Rejected | OK |
| 0279CA | 2026-05-19 | Accepted | — | — | — | — | Rejected | OK |
| 3317CA | 2026-05-19 | Accepted | — | — | — | — | Rejected | OK |
| 0390RE | 2026-05-19 | Accepted | — | — | — | — | Rejected | OK |
| 0496UP | 2026-05-19 | Accepted | — | — | — | — | Rejected | OK |
| 0587UP | 2026-05-19 | Accepted | — | — | — | — | Rejected | OK |
| 0548CA | 2026-05-20 | Accepted | — | — | — | — | Rejected | OK |
| 3907CA | 2026-05-20 | Rejected | 15.79 | -0.14 | 0.54 | 30.00 | Rejected | OK |
| 0479RE | 2026-05-20 | Accepted | — | — | — | — | Rejected | OK |
| 0596SI | 2026-05-20 | Accepted | 0.00 | 0.24 | 0.58 | 98.00 | Rejected | OK |
| 0098SI | 2026-05-20 | Accepted | — | — | — | — | Rejected | OK |
| 0301RE | 2026-05-20 | Accepted | 0.00 | 0.12 | 0.00 | 127.00 | Rejected | OK |
| 0926UP | 2026-05-20 | Accepted | 0.00 | 0.29 | 0.36 | 21.00 | Rejected | OK |
| 4653CA | 2026-05-21 | Accepted | — | — | — | — | Rejected | OK |
| 4062CA | 2026-05-21 | Accepted | — | — | — | — | — | OK |
| 0051RE | 2026-05-21 | Accepted | — | — | — | — | Rejected | OK |
| 4663UP | 2026-05-21 | Accepted | 0.00 | 0.46 | 0.58 | 20.00 | Rejected | OK |
| 0941AL | 2026-05-22 | Accepted | — | — | — | — | Rejected | OK |
| 0624RE | 2026-05-22 | Accepted | — | — | — | — | Rejected | OK |
| 0043SI | 2026-05-22 | Accepted | — | — | — | — | Rejected | OK |
| 0039SI | 2026-05-23 | Accepted | — | — | — | — | Rejected | OK |
| 0099SI | 2026-05-23 | Accepted | — | — | — | — | Rejected | OK |
| 1109CA | 2026-05-24 | Accepted | — | — | — | — | Rejected | OK |
| 4555CA | 2026-05-24 | Accepted | — | — | — | — | Rejected | OK |
| 0221UP | 2026-05-24 | Accepted | — | — | — | — | Rejected | OK |
| 4061UP | 2026-05-25 | Accepted | — | — | — | — | Rejected | OK |
| 0931CA | 2026-05-25 | Accepted | — | — | — | — | Rejected | OK |
