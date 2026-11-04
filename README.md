# Traffic-AI - Adaptive Traffic Signal Optimization on Pune Junction Data

XGBoost short-term demand prediction + Genetic Algorithm signal timing + Fixed-Time vs Adaptive simulation, with a React dashboard on a FastAPI backend.
**It does not control real signals and does not show live traffic.** Observed data, ML predictions, simulation estimates and assumptions are labelled separately in the UI.

## Dataset and attribution
**Heterogeneous Traffic Count Dataset, Pune (Jan 2023)** - Mendeley Data, DOI [10.17632/xnf2k6n288.1](https://doi.org/10.17632/xnf2k6n288.1), <https://data.mendeley.com/datasets/xnf2k6n288/1>.
Contributors: Ashwini Matange and Jibi Abraham. Collection period: January 11-18, 2023. License: CC BY 4.0.
**This project uses 100,000 selected records of the original dataset, not the complete dataset.**

File: `data/raw/Pune_Traffic_100000_records_with_metadata.csv` (never modified). Columns: `Date, Time, Direction, car, motorbike, bus, truck, Junction, Camera, SourceFile`.
- **Verified by the pipeline:** exactly 100,000 valid rows, no missing values, 3 junctions (AlankarChowk, JehangirChowk, RTOChowk), 8 cameras, 115 source files, 1,003 s of rows.
- **Date** is derived from the source filename (e.g. `a2_11` = camera a2, 11 Jan 2023) and covers 2023-01-11 to 2023-01-18 (8 days, one date per file).
- **Time** is the start timestamp of the aggregation interval (dataset documentation as supplied by the project owner); it covers 08:59-11:29.
- **Direction:** UP, DOWN, LEFT and RIGHT are the documented vehicle movement directions through the junction. How they map to signal phases is still an *assumption* of the simulation (each direction = one phase).
- **Counts:** the stored values are used unchanged. In this file every class column is non-decreasing inside each file/direction (0 of 1,840 series decrease), so a file's vehicles are computed as last value - first value (760 vehicles in total); adding up the rows would count the same vehicle many times. Interval-wise counts that were summed would give a very different, inflated total, so this is checked, not assumed.
- 95,040 identical rows are repeated frames; they are kept.
- **Limitation:** Limited Junction Coverage - the dataset covers only three traffic junctions in Pune. Model performance may vary when applied to other junctions.
- The full report is at the bottom of the Dashboard ("Data Quality Report") and in `data/processed/data_quality_report.json`.

## Methods
- **Preprocessing** (`backend/preprocessing.py`, rerun with `python -m backend.preprocessing`): validates rows, estimates fps (25), builds a per-clip table and 1-second arrival bins (`data/processed/`).
- **Peak analysis** (`backend/analysis.py`): `Date`, `Camera`, `Junction` and `SourceFile` are kept in every processed table, and a clip is identified by Date + SourceFile + Time. *Observed* vehicles are counted per clip; an *estimated* hourly-equivalent rate = vehicles / sampled video seconds x 3600 (a few seconds of video extrapolated to one hour, so it is never a measured hourly count). Video seconds = rows / ~25 per second per direction; the CSV has no separate duration field. Results: **date-wise** (junction x date, and junction x date x clock window A/B; dates are never merged) and **aggregated across selected dates** (clock minute, direction, class, window A/B). The busiest observed window is reported with its real date and clip start times, with a caution when one clip holds >= 50% of its vehicles. Minutes with < 3 clips are not rated; no missing minutes are filled in. The busiest period is the highest in the available video samples, not Pune's rush hour.
- **Vehicle counts:** the documentation describes per-interval counts, but in the selected CSV every class column only rises inside its (file, direction) sequence (0 of 1,840 decrease; 99.6-99.9% of consecutive rows are equal; steps are 1-2; 459 of 460 sequences start at 0; reading the rows as intervals and summing them would give 79,950 vehicles instead of 760, i.e. each vehicle ~100 times). Vehicles are therefore the **sum of increases inside each sequence** (a decrease would be treated as a counter reset; none occurs), never across clips. Stored values are unchanged. The original Mendeley README/data dictionary were not available to compare, so this is the data-based reading and is shown on the Peak-Hour page as "Count Basis".
- **Prediction** (`backend/model.py`): target = vehicles arriving in the next 1-4 s per direction. Features: junction, direction, arrivals in the last 3 s, other directions, vehicle categories. Split by clip in time order 70/15/15 (validation only for XGBoost early stopping; test untouched). Compared with Linear Regression, Random Forest and two baselines. Test metrics, horizon 3 s: XGBoost MAE 0.453 / RMSE 0.694 / R² 0.185; Random Forest 0.443 / 0.689 / 0.198; Linear 0.455 / 0.704 / 0.160; historical-mean baseline 0.568 / 0.771 / -0.007; recent-rate baseline **0.344** / 0.810 / -0.110. Counts over a few seconds are mostly zero, so R² is low and the simple recent-rate baseline wins on MAE. Reported as it is.
- **Genetic Algorithm** (`backend/genetic_algorithm.py`): 4 greens, cycle 120 s, min 10 s, max 60 s, lost time 4 s/phase (all configurable), greens + lost time = cycle. Objective = demand-weighted HCM-style delay (uniform + incremental) + congestion penalty for degree of saturation > 0.95. Fixed-Time plan is in the starting population, so the GA is never worse than it by the formula.
- **Simulation** (`backend/simulator.py`): 1-s steps, Poisson arrivals per vehicle class at observed rates x multiplier, individual vehicles in per-direction queues, buses/trucks need more discharge capacity (PCU 1 / 0.5 / 3.7 / 3.7). Same seed = identical arrivals for both controllers. **Fixed-Time** keeps an equal split (or a GA plan for the overall observed demand). **Adaptive** re-plans every cycle: XGBoost predicts demand from the last 60 s of arrivals, the GA picks greens; the first cycle uses the Fixed-Time plan.
- **Metrics:** average / maximum waiting time (vehicles still queued count their wait so far), average / maximum queue, vehicles served, throughput, congestion (% of time a queue >= 15 vehicles), and Waiting-Time Reduction (%) = (Fixed - Adaptive) / Fixed x 100 (None if Fixed = 0). Negative values are shown honestly.
- **Assumptions (editable per run in the UI; defaults in `frontend/src/hooks/useSettings.js`):** saturation flow 3,600 PCU/h per phase (2 lanes), PCU weights, lost time, demand multiplier, congestion queue. None are measured in Pune.

## Run it
Python 3.11+ and Node 18+.
```bash
# backend (from the project folder)
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m backend.model                                 # optional: retrain (models/ already included)
uvicorn backend.main:app --reload --port 8000

# frontend (second terminal)
cd frontend && npm install && npm run dev               # http://localhost:5173
```
Create an account on the login page (first run). Tests: `python -m pytest -q` (49 tests). Size check: `python scripts/count_loc.py` (limit 3,000 lines).

## Demo script
1. Dashboard: KPIs, charts and a default Fixed vs Adaptive result come from the backend.
2. Peak-Hour Analysis: observed vs estimated, date-wise table and charts, aggregated views, busiest observed window, limitations.
3. Prediction and Model Comparison: actual vs predicted, honest baselines.
4. Signal Optimization: choose junction/period, optimize, read the "why" and the limitations; try *manual* what-if demand (marked hypothetical).
5. Live Simulation: Start / Pause / Resume / Reset, queues drawn from backend state; then Waiting-Time Analytics: *Run peak vs off-peak*.
6. Experiment History: every run is saved; tick two rows to compare; clear needs confirmation.

## Known limitations
Only 3 junctions (Limited Junction Coverage) and about 17 minutes of rows; noisy low-count prediction (R² ≤ 0.2); layout of directions assumed; saturation flow and PCU are assumptions; at high demand both controllers are over capacity and show little difference (shown, not hidden); no SUMO (impractical without trajectories or a road network); simulated results are not field measurements.
