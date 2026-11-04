# Audit of the original Traffic-AI project (before the upgrade)

**Already worked (kept or adapted):** FastAPI app with JWT-style login (`auth.py`, kept unchanged), SQLite via SQLAlchemy (`db.py`, kept, run table
generalised), Genetic Algorithm (`genetic_algorithm.py`: repair, tournament, elitism, constraint checks - kept, delay model replaced), one-second
queue simulator with shared random arrivals per seed (idea kept, rewritten), React + Vite + Tailwind + Recharts + Lucide + Framer Motion (kept),
WebSocket simulation stream (kept, now with pause/resume).

**Missing for the new brief:** peak analysis, vehicle categories, per-direction queues, waiting-time/queue analytics page, experiment history UI,
what-if analysis, explainable recommendations, model comparison page, dark premium UI, tests for all of this.

**Dataset compatibility problems (the big finding).** The old code expected hourly counts of 4 numbered junctions with dates. The Pune CSV is different:

| Fact (computed by `backend/preprocessing.py`) | Consequence |
|---|---|
| 100,000 rows = video **frames** of 115 clips (~8.7 s each, ~25 fps), 3 junctions, 4 directions | Rows are not independent observations. |
| car/motorbike/bus/truck are **cumulative counters** inside a clip (0 of 1,840 series ever decrease) | Vehicles of a clip = last - first. Summing rows would over-count about 100x. The CSV holds only 760 vehicles in total. |
| `Time` is a clock time (08:59-11:29); the updated CSV adds a `Date` (2023-01-11 to 2023-01-18, from the filenames) and `Camera` | Each file holds only seconds of rows, so there is no 24-hour profile; peaks are pooled by clock minute. (Written for the first CSV, which had no Date.) |
| 95,040 exact duplicate rows | Repeated all-zero frames; kept, not dropped. |
| One clip (a3_18_one, Alankar) holds 149 of 760 vehicles | Reported as a caution; Alankar's "peak" is dominated by it. |

**Modelling problems avoided:** the old hourly lag features (24 h, 168 h), weekday/month features and the 4-junctions-as-one-intersection assumption cannot
be used. New target: vehicles arriving in the next H seconds; features use only seconds up to t; train/validation/test are split by clip in time order.

**Decisions:** old `traffic.csv` / `traffic_ai.csv` and the old notebooks were removed (different dataset, would mislead). Stale DB and secret key were not shipped.
