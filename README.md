# Traffic-AI
### AI-Based Adaptive Traffic Signal Optimization Using XGBoost and Genetic Algorithm

Traffic-AI is a research-oriented traffic signal optimization project that combines short-term vehicle-arrival prediction, Genetic Algorithm (GA)-based signal timing, and a traffic simulation environment. It compares a conventional fixed-time signal plan with an adaptive plan that periodically adjusts green-signal durations using predicted traffic demand.

The application provides a React dashboard backed by a FastAPI service. It is designed for analysis and simulation using a selected Pune traffic dataset.

> **Important:** This project is a simulation and decision-support prototype. It does **not** connect to or control real traffic signals, and it does **not** provide live traffic-camera feeds or live city traffic measurements. Dashboard values are identified as observed data, model predictions, simulation outputs, or configurable assumptions.

---

## Contents

- [Project Highlights](#project-highlights)
- [System Workflow](#system-workflow)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Dataset and Attribution](#dataset-and-attribution)
- [Machine Learning and Optimization](#machine-learning-and-optimization)
- [Simulation and Evaluation](#simulation-and-evaluation)
- [Installation and Setup](#installation-and-setup)
- [Running the Application](#running-the-application)
- [API Overview](#api-overview)
- [Tests and Code Size](#tests-and-code-size)
- [Assumptions and Limitations](#assumptions-and-limitations)
- [Future Scope](#future-scope)
- [License and Credits](#license-and-credits)

---

## Project Highlights

- **Traffic data preprocessing:** validates the selected dataset and creates clip-level and one-second arrival data.
- **Short-term traffic prediction:** predicts vehicle arrivals over the next 1–4 seconds for each direction.
- **Model comparison:** compares XGBoost, Random Forest, Linear Regression, and simple baselines.
- **Adaptive signal timing:** uses a Genetic Algorithm to select green durations based on estimated traffic demand.
- **Fixed-Time vs Adaptive comparison:** evaluates both controllers under the same simulated arrival stream.
- **Traffic simulation:** models directional queues, vehicle discharge, waiting time, and congestion.
- **Peak-Hour Analysis:** explores the busiest periods found in the available video samples, with date-wise and aggregated views.
- **Analytics dashboard:** presents prediction, optimization, simulation, and experiment-history results.
- **Experiment history:** saves simulation/experiment results for later review and comparison.
- **User authentication:** provides registration and login endpoints for the application.

---

## System Workflow

```text
Selected Pune Traffic Dataset
             |
             v
     Data Preprocessing
             |
             +----------------------+
             |                      |
             v                      v
    Clip-Level Data          1-Second Arrivals
             |                      |
             +----------+-----------+
                        |
                        v
             Traffic Demand Features
                        |
                        v
              ML Model Prediction
                        |
                        v
             Genetic Algorithm
             Signal-Time Selection
                        |
             +----------+-----------+
             |                      |
             v                      v
       Fixed-Time Plan        Adaptive Plan
             |                      |
             +----------+-----------+
                        |
                        v
               Traffic Simulation
                        |
                        v
       Waiting Time / Queue / Throughput
                        |
                        v
                 React Dashboard
```

---

## Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS |
| Charts and visualization | Recharts |
| UI and animation | Lucide React, Framer Motion |
| Frontend API requests | Axios |
| Backend | Python, FastAPI, Uvicorn |
| Machine Learning | XGBoost, Scikit-learn |
| Data processing | Pandas, NumPy |
| Model persistence | Joblib |
| Database layer | SQLAlchemy |
| Testing | Pytest, HTTPX |

---

## Project Structure

```text
Traffic-AI/
├── backend/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application and API routes
│   ├── auth.py                 # Authentication helpers
│   ├── db.py                   # Database configuration and operations
│   ├── preprocessing.py        # Dataset validation and preprocessing
│   ├── model.py                # Model training and prediction utilities
│   ├── analysis.py              # Peak-hour and traffic analysis
│   ├── genetic_algorithm.py    # GA-based signal timing optimization
│   └── simulator.py            # Fixed-time and adaptive simulation
│
├── data/
│   ├── raw/
│   │   └── Pune_Traffic_100000_records_with_metadata.csv
│   └── processed/
│       ├── clips.csv
│       ├── arrivals_1s.csv
│       └── data_quality_report.json
│
├── docs/
│   └── AUDIT.md
│
├── frontend/
│   ├── src/
│   │   ├── api/                # Backend API client
│   │   ├── components/         # Shared UI and chart components
│   │   ├── hooks/              # Reusable React hooks
│   │   ├── pages/              # Dashboard and feature pages
│   │   ├── App.jsx
│   │   ├── index.css
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
│
├── models/
│   ├── xgb_models.joblib
│   └── model_report.json
│
├── scripts/
│   └── count_loc.py
├── tests/
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Dataset and Attribution

This project uses a **selected subset of 100,000 records** from the following source:

**Heterogeneous Traffic Count Dataset, Pune (January 2023)**  
- Contributors: Ashwini Matange and Jibi Abraham
- Source: [Mendeley Data](https://data.mendeley.com/datasets/xnf2k6n288/1)
- DOI: [10.17632/xnf2k6n288.1](https://doi.org/10.17632/xnf2k6n288.1)
- Collection period: January 11–18, 2023
- Dataset license: CC BY 4.0

### Dataset file used

```text
data/raw/Pune_Traffic_100000_records_with_metadata.csv
```

The selected file contains these columns:

`Date, Time, Direction, car, motorbike, bus, truck, Junction, Camera, SourceFile`

The selected records cover three Pune junctions:
- Alankar Chowk
- Jehangir Chowk
- RTO Chowk

The data includes four movement directions: `UP`, `DOWN`, `LEFT`, and `RIGHT`.

### Data interpretation notes

- The project uses 100,000 selected records, not the complete original dataset.
- The `Date` field is derived from the source filename; the selected files cover January 11–18, 2023.
- `Time` represents the start timestamp of the aggregation interval, according to the dataset information available to the project.
- The selected file contains repeated rows and short video observations. It should not be interpreted as continuous, full-day traffic monitoring.
- The pipeline uses the stored vehicle-count sequences and derives clip-level vehicle totals from changes within each file/direction sequence. This interpretation is based on the observed sequence behaviour in the selected file; it should be treated as a project data-processing decision, not as a universal property of all traffic-count datasets.
- Direction-to-signal-phase mapping is a simulation assumption.

The application includes a Data Quality Report to communicate dataset coverage and interpretation constraints.

---

## Machine Learning and Optimization

### 1. Traffic prediction

The prediction task estimates vehicle arrivals in the next **1–4 seconds** for a selected junction and direction.

The model features include:
- Junction and direction
- Recent arrivals over the previous three seconds
- Recent arrivals from other directions
- Vehicle-category information

The project compares:
- XGBoost
- Random Forest
- Linear Regression
- Historical-mean baseline
- Recent-rate baseline

The data split is performed in clip/time order, with separate training, validation, and test portions. The test set is kept separate from XGBoost early stopping.

### Reported model comparison

The current model report records the following test metrics for a 3-second prediction horizon:

| Model | MAE | RMSE | R² |
|---|---:|---:|---:|
| XGBoost | 0.453 | 0.694 | 0.185 |
| Random Forest | 0.443 | 0.689 | 0.198 |
| Linear Regression | 0.455 | 0.704 | 0.160 |
| Historical-mean baseline | 0.568 | 0.771 | -0.007 |
| Recent-rate baseline | **0.344** | 0.810 | -0.110 |

These are the metrics recorded in the project's current README/model report context. The low R² values indicate that short-horizon counts are difficult to predict reliably in this selected sample. The recent-rate baseline has the lowest MAE, so the project reports that result rather than claiming XGBoost is best on every metric.

### 2. Genetic Algorithm

The Genetic Algorithm searches for signal green-time allocations under configurable constraints.

Current default configuration described by the project:
- Four directional green phases
- Cycle length: 120 seconds
- Minimum green: 10 seconds
- Maximum green: 60 seconds
- Lost time: 4 seconds per phase

The objective combines a demand-weighted HCM-style delay estimate with a congestion penalty when the degree of saturation exceeds 0.95. The fixed-time plan is included in the initial population so that the GA result is not worse than the fixed-time plan according to the optimizer's objective function.

---

## Simulation and Evaluation

The simulator advances in one-second steps and creates simulated vehicle arrivals using Poisson rates derived from observed arrival rates and a configurable demand multiplier.

Both controllers receive the same simulated arrival stream when the same random seed is used.

### Controllers

- **Fixed-Time:** uses an equal green-time split, or a GA plan for the overall observed demand, depending on the selected run configuration.
- **Adaptive:** uses recent arrivals to predict near-term demand and asks the Genetic Algorithm to update green times at cycle boundaries. The first cycle starts with the fixed-time plan.

### Reported metrics

- Average and maximum waiting time
- Average and maximum queue length
- Vehicles served
- Throughput
- Congestion percentage
- Waiting-time reduction compared with the fixed-time controller

Vehicles that remain queued contribute their waiting time accumulated so far. A negative waiting-time reduction is possible and is displayed honestly; it means the adaptive simulation performed worse for that run.

### Configurable assumptions

The UI exposes simulation assumptions such as:
- Saturation flow
- Passenger-car-unit (PCU) weights
- Lost time
- Demand multiplier
- Congestion queue threshold

These are configurable simulation parameters, not measurements collected from Pune roads.

---

## Installation and Setup

### Prerequisites

- Python 3.11 or newer
- Node.js and npm (use a version compatible with the installed Vite release)
- Git

### 1. Clone the repository

```bash
git clone https://github.com/code-dev-007/AI-Based-Adaptive-Traffic-Signal-Optimization.git
cd AI-Based-Adaptive-Traffic-Signal-Optimization
```

### 2. Create and activate a Python virtual environment

**Windows (Command Prompt):**

```cmd
python -m venv .venv
.venv\Scripts\activate
```

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux / macOS / WSL:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install backend dependencies

Run this command from the project root:

```bash
pip install -r requirements.txt
```

### 4. Install frontend dependencies

Open a second terminal:

```bash
cd frontend
npm install
```

Do not commit or upload `node_modules/`; it is recreated from `package.json` and `package-lock.json`.

---

## Running the Application

Start the backend from the **project root** in the first terminal:

```bash
uvicorn backend.main:app --reload --port 8000
```

Backend:
- API base: `http://127.0.0.1:8000`
- Interactive API documentation: `http://127.0.0.1:8000/docs`

Start the frontend in the second terminal:

```bash
cd frontend
npm run dev
```

Frontend:
- `http://localhost:5173`

Keep both terminals running while using the application.

### Optional: preprocess the dataset

From the project root:

```bash
python -m backend.preprocessing
```

### Optional: retrain the prediction models

Pre-trained model files are included in `models/`. To retrain:

```bash
python -m backend.model
```

Run preprocessing before retraining if the processed data needs to be regenerated.

---

## API Overview

The FastAPI backend exposes API routes for the following application functions:

| Area | Functionality |
|---|---|
| Authentication | Register, login, and current-user lookup |
| Health | Backend health check |
| Dataset | Dataset summary and data information |
| Peak analysis | Peak-hour and traffic sample analysis |
| Prediction | Short-term directional arrival prediction |
| Model comparison | Compare prediction models and baselines |
| Optimization | Calculate optimized signal timing |
| Experiments | Run and save controller comparison experiments |
| Dashboard | Dashboard simulation summary |
| History | Retrieve, inspect, and clear saved experiment history |
| Simulation | Start, step, pause, resume, reset, and inspect simulation |
| WebSocket | Stream simulation state updates |

For exact request and response schemas, run the backend and open:

`http://127.0.0.1:8000/docs`

---

## Tests and Code Size

Run backend tests from the project root:

```bash
python -m pytest -q
```

Check the project's application code line count:

```bash
python scripts/count_loc.py
```

The project is intended to stay within a **3,000-line application-code limit**. Generated files, dependency folders, datasets, and other excluded files should not be counted as application source code; follow the counting script's exclusions.

---

## Assumptions and Limitations

1. **Limited junction coverage:** the selected dataset contains only three Pune junctions.
2. **Short observation coverage:** the source contains short video samples, not continuous 24-hour observations.
3. **Estimated hourly-equivalent rates:** scaling short samples to an hourly equivalent is an estimate, not a measured hourly traffic count.
4. **Observed peak window:** the busiest window represents the available samples, not necessarily Pune's actual daily or city-wide rush hour.
5. **Prediction uncertainty:** low-count, short-horizon observations produce noisy targets; model metrics, including weak R² values, are shown transparently.
6. **Signal-phase assumption:** mapping UP/DOWN/LEFT/RIGHT movements to four independent signal phases is a simulation assumption.
7. **Simulation parameters:** saturation flow, PCU weights, lost time, and demand multipliers are assumptions/configurable values, not field measurements.
8. **No live control:** the application does not control traffic lights or connect to live road infrastructure.
9. **No field validation:** simulated waiting times, queue lengths, and throughput are not real-world measurements.
10. **Traffic simulator scope:** the project uses its own queue-based simulator and does not currently use SUMO or a calibrated road-network model.

---

## Future Scope

- Validate the approach with longer-duration and more geographically diverse traffic datasets.
- Improve prediction using richer temporal and contextual features.
- Validate signal-phase mapping and simulation parameters with real junction geometry and signal plans.
- Integrate a calibrated microscopic traffic simulator for more realistic evaluation.
- Explore deployment and monitoring workflows after appropriate safety, reliability, and field validation.

---

## License and Credits

### Dataset credit

The traffic dataset is credited to Ashwini Matange and Jibi Abraham and is distributed through Mendeley Data under **CC BY 4.0**. Please refer to the [original dataset page](https://data.mendeley.com/datasets/xnf2k6n288/1) and its license terms when reusing the source data.

### Project

**Traffic-AI — AI-Based Adaptive Traffic Signal Optimization Using XGBoost and Genetic Algorithm**

Repository: [code-dev-007/AI-Based-Adaptive-Traffic-Signal-Optimization](https://github.com/code-dev-007/AI-Based-Adaptive-Traffic-Signal-Optimization)

---

<p align="center">
  Built as an academic project to explore machine learning, traffic simulation, and adaptive signal timing.
</p>
