# Research statistics and exports

TopRanker runs every submission on the same grid: 3 instances x 5 seeds on a problem
and dimension, with the same budget. Because of that, two submissions can be compared
run by run, the way benchmarking studies compare optimizers (COCO/BBOB,
IOHprofiler). The research page (`/research`) does this for up to eight entries, and
every number behind it can be downloaded.

All statistics use public data only: the AOCC and the precision of each run. Raw
objective values, reference values and held-out contest results are never used.

## The comparison

Choose a problem and a dimension. The page lists each person's best submission (and the
baselines), with the top three people and the baselines ticked. "Compare" calls
`GET /api/research/compare?problem_id=STD-004&dim=10&ids=12&ids=40&ids=41`.

| Measure | What it is | How to read it |
|---|---|---|
| Mean AOCC (95% CI) | Mean of the per-run AOCC, with a percentile bootstrap interval (2000 resamples, fixed seed) | Overlapping intervals mean the difference may be noise |
| Median AOCC | Median of the per-run AOCC | Less affected by one bad run |
| Mean rank | Each of the shared runs (same instance and seed) ranks the entries, 1 being best; this is the average | Lower is better |
| Friedman test | Whether all entries perform alike over the shared runs (three or more entries) | A small p (below 0.05) means at least one differs |
| Mann-Whitney U | Two-sided test on per-run AOCC for each pair | Raw p-value |
| p (Holm) | The p-value corrected for the number of pairs (Holm-Bonferroni) | Used for the verdict |
| A12 | Vargha-Delaney effect size: the probability that a run of the first entry scores higher than a run of the second | 0.5 means no difference; 0.56, 0.64 and 0.71 are the usual small, medium and large thresholds |
| ECDF | Share of (run, target) pairs reached after a number of evaluations, for the 11 targets 1e2, 1e1, ... 1e-8 | Higher and further left is better; a failed run reaches nothing |

A pair is called significantly different when its Holm-corrected p-value is below 0.05;
the entry with A12 above 0.5 is then reported as better. With 15 runs per entry, small
differences will often not be significant: that is the honest answer, not a defect.

The functions are in `backend/research/stats.py` and are covered by
`backend/tests/test_research.py`.

## Downloads

Every table is offered as CSV (for spreadsheets, R or pandas) and JSON. Add
`format=json` for JSON; CSV is the default.

| What | Endpoint | Columns |
|---|---|---|
| Runs of one submission | `GET /api/submissions/{id}/export` | `instance_seed, seed, status, evals, aocc, precision, wall_sec`, then `precision_at_<evaluations>` for each of the up to 64 checkpoints |
| Runs of compared entries | `GET /api/research/runs?problem_id=&dim=&ids=&ids=` | `submission_id, name, is_baseline` and the columns above, one row per run (long format) |
| Problem leaderboard | `GET /api/problems/{id}/leaderboard/export?dim=` | `rank, user_id, name, country, institution, is_baseline, submission_id, score, median_precision, iqr, submitted_at` |
| Contest ranking | `GET /api/contests/{id}/leaderboard/export` | `rank, user_id, name, is_baseline, final, total`, then one column per task (`problem@dim`) |

Two more formats are offered for a comparison on the research page:

| What | Endpoint | Contents |
|---|---|---|
| LaTeX table | `GET /api/research/latex?problem_id=&dim=&ids=&ids=` | A `booktabs` table: runs, mean AOCC with its 95% interval, median and mean rank per entry; the best mean is bold. Needs `\usepackage{booktabs}` |
| IOHanalyzer | `GET /api/research/ioh?problem_id=&dim=&ids=&ids=` | A zip with one folder per entry in the IOHprofiler format (a `.json` file and a `.dat` file of improvements). `raw_y` is the precision, so the target is 0. Upload the zip to IOHanalyzer to get its fixed-target and fixed-budget plots |

Code, logs and error messages are never included in an export. The download links are
on the submission page (Runs), the problem page (Leaderboard tab), the contest page and
the research page.

Example in Python:

```python
import pandas as pd

runs = pd.read_csv("http://localhost:3000/api/research/runs"
                   "?problem_id=STD-004&dim=10&ids=12&ids=40")
print(runs.groupby("name")["aocc"].describe())
```
