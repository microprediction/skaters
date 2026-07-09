# Pre-registered studies

Every new challenger bout gets a statement of intended research filed here
**before the results are read**. The statement freezes the protocol, the
parameters, the analysis plan, and the reporting commitments, and discloses
exactly what had already been observed at filing time. The git commit is the
timestamp.

Why we do this. Forecasting research has a long record of results that could
not be reproduced, and the field's own journals have asked for exactly this
discipline: the International Journal of Forecasting's editors called for
replicable and reproducible research (Hyndman 2010), documented how hard
reproduction is even with the original authors cooperating (Boylan, Goodwin,
Mohammadipour and Syntetos 2015), and credited the forecasting competitions'
influence precisely to their protocols being fixed before the results existed
(Hyndman 2020; Makridakis, Spiliotis and Assimakopoulos 2020). The broader
open-science case for pre-registration is made by Nosek, Ebersole, DeHaven
and Mellor (2018), and machine learning has run the same experiment with the
NeurIPS pre-registration workshop (2020). A benchmark run by the authors of
one of the methods being benchmarked deserves more suspicion, not less, so
the protocol goes on the record first.

The rules a statement must satisfy:

1. Filed and committed before the run completes, with a disclosure section
   listing every number already observed at filing time.
2. The harness is committed in the same commit, and the statement's frozen
   parameters must match the harness defaults.
3. Outcome-neutral hypotheses and a fixed analysis plan, including the exact
   test and significance level.
4. A reporting commitment: all rows are published at the same volume whether
   our method wins or loses, and every surface that summarizes the study is
   updated in the same pass.
5. Any deviation after filing is logged in the statement's deviations
   section, dated, with the reason. Silent changes are not allowed.

## Filed statements

- [2026-07-09 — TabFM (Google) vs laplace](2026-07-09-tabfm.md), harness
  `benchmarks/tabfm_study.py`.

## References

- Boylan, J.E., Goodwin, P., Mohammadipour, M., Syntetos, A.A. (2015).
  Reproducibility in forecasting research. *International Journal of
  Forecasting* 31(1), 79-90.
- Hyndman, R.J. (2010). Encouraging replication and reproducible research.
  *International Journal of Forecasting* 26(1), 2-3.
- Hyndman, R.J. (2020). A brief history of forecasting competitions.
  *International Journal of Forecasting* 36(1), 7-14.
- Makridakis, S., Spiliotis, E., Assimakopoulos, V. (2020). The M4
  Competition: 100,000 time series and 61 forecasting methods.
  *International Journal of Forecasting* 36(1), 54-74.
- Nosek, B.A., Ebersole, C.R., DeHaven, A.C., Mellor, D.T. (2018). The
  preregistration revolution. *PNAS* 115(11), 2600-2606.
- NeurIPS 2020 Workshop on Pre-registration in Machine Learning.
