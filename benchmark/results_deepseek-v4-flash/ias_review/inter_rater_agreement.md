# Inter-rater agreement (IAS)

- Raters: rater_1_completed.csv, rater_2_completed.csv
- Commonly-rated decisions: **367**
- Category space: appropriate, should_have_intervened, unnecessary
- Target: Cohen's kappa ≥ **0.7** (CadisClaude §9.3 step 5 / newplan §13)

## Cohen's kappa (pairwise)

| pair | n | p_o (raw agreement) | p_e | kappa | meets target |
|---|---|---|---|---|---|
| rater_1_completed.csv vs rater_2_completed.csv | 367 | 0.6049 | 0.3761 | 0.3667 | **no** |

## Disagreements: 145

See `reconciliation_worksheet.csv`. An adjudicator fills `reconciled_rating`, saves `blind_id,reconciled_rating` as `reconciled.csv`, then re-run `score --reconciled reconciled.csv`.

## Per-condition IAS (from consensus)

| condition | n | appropriate | should_have_intervened | unnecessary | appropriate_frac |
|---|---|---|---|---|---|
| cadis | 80 | 55 | 9 | 16 | 0.6875 |
| full_autonomy | 35 | 23 | 12 | 0 | 0.6571 |
| random | 58 | 38 | 8 | 12 | 0.6552 |
| static_hitl | 194 | 73 | 4 | 117 | 0.3763 |

> IAS is **secondary/supporting** evidence and does not redefine the primary endpoints (newplan §12).
