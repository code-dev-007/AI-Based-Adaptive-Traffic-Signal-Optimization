"""FastAPI service for Traffic-AI. Start with:  uvicorn backend.main:app --reload

Every response says what kind of numbers it holds:
  observed  = computed from the Pune CSV (vehicle counts of short video clips)
  predicted = XGBoost output
  simulated = simulator / Genetic Algorithm estimates (queues, waits, signal timings)
"""
import asyncio
import logging
import re
import uuid
from dataclasses import asdict
from typing import Literal

import numpy as np
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend import analysis, auth, db
from backend import genetic_algorithm as ga
from backend import model as ml
from backend import preprocessing as pp
from backend import simulator as sm

app = FastAPI(title="Traffic-AI API", version="1.0.0",
              description="Pune traffic analysis, XGBoost demand prediction, Genetic Algorithm signal timing and Fixed-Time vs Adaptive simulation.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
log = logging.getLogger("traffic_ai")
db.init_db()
protected = APIRouter(dependencies=[Depends(auth.require_user)])  # every route on it needs a valid login token
_cache: dict = {}                                                  # data, model and analysis results kept in memory
_sim: dict = {"sim": None, "meta": {}}                              # the one live simulation and how it was started
AUTO_NOTE = "SIMULATED estimates: observed Pune counts only set the arrival rates. Not live traffic, not field measurements."


# ---------------------------------------------------------------- request bodies
class Credentials(BaseModel):
    username: str
    password: str


class Timing(BaseModel):
    cycle_length: int = Field(default=ga.CYCLE_LENGTH, ge=20, le=300)
    min_green: int = Field(default=ga.MIN_GREEN, ge=1, le=120)
    max_green: int = Field(default=ga.MAX_GREEN, ge=1, le=240)
    lost_time: int = Field(default=ga.LOST_TIME, ge=0, le=15)
    saturation_flow: float = Field(default=ga.SATURATION_FLOW, gt=0, le=20000)  # PCU/h of green per phase (assumption)
    fixed_plan: Literal["equal", "historical"] = "equal"


class Scenario(Timing):
    junction: str
    period: str = "all"
    multiplier: float = Field(default=1.0, gt=0, le=5)


class SimBody(Scenario):
    duration: int = Field(default=1800, ge=60, le=7200)
    reopt_s: int = Field(default=ga.CYCLE_LENGTH, ge=10, le=3600)
    congestion_queue: int = Field(default=15, ge=1, le=500)

    def config(self) -> sm.Config:
        return sm.Config(**self.model_dump(include=set(sm.Config.__dataclass_fields__)))


class ExperimentBody(SimBody):
    n_seeds: int = Field(default=3, ge=1, le=10)
    base_seed: int = 42
    name: str = Field(default="", max_length=60)


class StartBody(SimBody):
    controller: Literal["fixed", "adaptive"] = "adaptive"
    seed: int = 42


class OptimizeBody(Scenario):
    source: Literal["observed", "predicted", "manual"] = "predicted"
    manual_vph: list[float] | None = None            # hypothetical vehicles/hour for UP, DOWN, RIGHT, LEFT
    population_size: int = Field(default=40, ge=10, le=200)
    generations: int = Field(default=60, ge=5, le=300)
    seed: int = 42


class StepBody(BaseModel):
    seconds: int = Field(default=10, ge=1, le=600)


# ---------------------------------------------------------------- loading helpers
def get_data() -> dict:
    if "data" not in _cache:
        try:
            _cache["data"] = pp.run_preprocessing()
        except (FileNotFoundError, ValueError) as error:
            raise HTTPException(status_code=503, detail=str(error))
    return _cache["data"]


def get_models() -> tuple[dict, dict]:
    if "model" not in _cache:
        try:
            _cache["model"] = ml.load_model()
        except ml.ModelNotFoundError as error:
            raise HTTPException(status_code=503, detail=str(error))
    return _cache["model"]


def get_samples():
    if "samples" not in _cache:
        _cache["samples"] = ml.build_samples(get_data()["arrivals"])
    return _cache["samples"]


def get_peak() -> dict:
    if "peak" not in _cache:
        data = get_data()
        _cache["peak"] = {**analysis.peak_analysis(data["clips"]), "rows_without_verified_date": data["report"]["invalid_rows"]["bad_date"]}
    return _cache["peak"]


def profile_for(junction: str, period: str) -> dict:
    try:
        return analysis.demand_profile(get_data()["clips"], junction, period)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Junction '{junction}' not found in the dataset.")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


def public(profile: dict) -> dict:
    return {k: v for k, v in profile.items() if k != "clip_names"}


def predicted_demand(profile: dict) -> list[float]:
    """PCU/h per direction: the saved XGBoost model applied to the real observed seconds of the selected clips."""
    models, report = get_models()
    samples = get_samples()
    rows = samples[samples["SourceFile"].isin(profile["clip_names"]) & (samples["t"] >= 2)]
    per_dir = rows.assign(p=np.clip(models[ml.CONTROL_HORIZON].predict(rows[ml.FEATURES]), 0, None)).groupby("direction")["p"].mean()
    return [float(per_dir.get(i, 0.0) / ml.CONTROL_HORIZON * 3600 * profile["pcu_per_vehicle"][d]) for i, d in enumerate(pp.DIRECTIONS)]


def run_config(body: SimBody) -> tuple[dict, dict, sm.Config]:
    return profile_for(body.junction, body.period), profile_for(body.junction, "all"), body.config()


def _record(kind: str, scenario: str, result: dict) -> int | None:
    try:
        return db.save_run(kind, scenario, result)
    except Exception as error:  # noqa: BLE001  a database problem must never break an API call
        log.warning("Could not save %s run: %s", kind, error)
        return None


def _saved_shape(name, controller, body, profile, metrics, extra=None) -> dict:
    return {"name": name, "controller": controller, "junction": body.junction, "period": body.period, "multiplier": body.multiplier,
            "duration_s": body.duration, "config": asdict(body.config()), "profile": public(profile), "metrics": metrics, **(extra or {})}


def _save_live_once(sim: sm.Simulation):
    if sim.saved or sim.t == 0:
        return
    sim.saved, meta = True, _sim["meta"]
    metrics = {m: {"mean": sim.metrics()[m], "std": 0.0} for m in sm.COMPARED}
    _record("simulation", meta["scenario"], {"name": f"Live: {meta['scenario']}", "controller": sim.controller, "junction": meta["junction"],
                                              "period": meta["period"], "multiplier": sim.cfg.multiplier, "duration_s": sim.t, "finished": sim.t >= sim.cfg.duration,
                                              "config": asdict(sim.cfg), "metrics": metrics, "seed": sim.seed})


def _advance(sim: sm.Simulation, seconds: int):
    if sim.running:
        sim.advance(seconds)
        sim.running = sim.t < sim.cfg.duration
        if not sim.running:
            _save_live_once(sim)


# ---------------------------------------------------------------- login (unchanged behaviour)
def _clean_username(raw: str) -> str:
    return raw.strip().lower()


@app.post("/api/v1/auth/register")
def register(credentials: Credentials):
    username = _clean_username(credentials.username)
    if not re.fullmatch(r"[a-z0-9_.-]{3,30}", username):
        raise HTTPException(status_code=400, detail="Username must be 3-30 characters: letters, numbers, dot, dash or underscore.")
    if len(credentials.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    if not db.create_user(username, auth.hash_password(credentials.password)):
        raise HTTPException(status_code=409, detail="That username is already taken.")
    return {"token": auth.create_token(username), "username": username}


@app.post("/api/v1/auth/login")
def login(credentials: Credentials):
    username = _clean_username(credentials.username)
    stored = db.get_password_hash(username)
    if stored is None or not auth.verify_password(credentials.password, stored):
        raise HTTPException(status_code=401, detail="Wrong username or password.")
    return {"token": auth.create_token(username), "username": username}


@app.get("/api/v1/auth/me")
def me(user: str = Depends(auth.require_user)):
    return {"username": user}


# ---------------------------------------------------------------- health, dataset, peak analysis
@app.get("/api/v1/health")
def health():
    status = {"status": "ok", "dataset_available": True, "model_available": True, "detail": []}
    for key, fn in (("dataset_available", get_data), ("model_available", get_models)):
        try:
            fn()
        except HTTPException as error:
            status[key] = False
            status["detail"].append(error.detail)
    if status["dataset_available"]:
        status["rows"] = get_data()["report"]["rows_valid"]
    return status


@protected.get("/api/v1/dataset")
def dataset():
    """Observed: data-quality report, limitations and the scenario choices the data supports."""
    data = get_data()
    return {"kind": "observed", "report": data["report"], "directions": pp.DIRECTIONS, "classes": pp.CLASSES, "pcu": pp.PCU,
            "periods": {j: analysis.list_periods(data["clips"], j) for j in data["report"]["junctions"]}}


@protected.get("/api/v1/peak-analysis")
def peak_analysis():
    return {"kind": "observed", **get_peak()}


@protected.get("/api/v1/scenario-profile")
def scenario_profile(junction: str, period: str = "all"):
    return {"kind": "observed", **public(profile_for(junction, period))}


# ---------------------------------------------------------------- prediction and model comparison
@protected.get("/api/v1/predict")
def predict(junction: str, direction: str, horizon: int = Query(3, ge=1, le=4), limit: int = Query(200, ge=1, le=1000)):
    """Actual vs predicted arrivals in the next `horizon` seconds, for clips the model never saw in training."""
    if direction not in pp.DIRECTIONS:
        raise HTTPException(status_code=400, detail=f"direction must be one of {pp.DIRECTIONS}.")
    models, report = get_models()
    if junction not in report["junction_codes"]:
        raise HTTPException(status_code=404, detail=f"Junction '{junction}' not found.")
    test = ml.split_predictions(models, get_samples(), horizon)
    rows = test[(test["Junction"] == junction) & (test["direction"] == pp.DIRECTIONS.index(direction))].sort_values(["start_s", "SourceFile", "t"])
    if rows.empty:
        raise HTTPException(status_code=404, detail="No held-out test samples for this junction and direction.")
    return {"kind": "predicted", "junction": junction, "direction": direction, "horizon_s": horizon,
            "metrics": ml.score(rows["actual"], rows["predicted"]), "overall_test_metrics": report["metrics"][str(horizon)]["XGBoost"]["test"],
            "items": [{"clip": r.SourceFile, "second": int(r.t), "actual": float(r.actual), "predicted": round(float(r.predicted), 3)} for r in rows.tail(limit).itertuples()],
            "note": f"Vehicles expected to arrive in the {horizon} s after each second of a clip. Held-out clips only; counts of a few seconds are noisy."}


@protected.get("/api/v1/model-comparison")
def model_comparison(horizon: int = Query(3, ge=1, le=4)):
    _, report = get_models()
    metrics = report["metrics"][str(horizon)]
    rows = [{"name": n, "kind": "baseline" if n.startswith("Baseline") else "model",
             "status": "no training (simple rule)" if n.startswith("Baseline") else "trained on training clips" + (", saved, early-stopped" if n == "XGBoost" else ""),
             **m["test"]} for n, m in metrics.items()]
    return {"kind": "evaluated", "horizon_s": horizon, "models": rows, "split": report["split"][str(horizon)], "split_method": report["split_method"],
            "trained_at": report["trained_at"], "note": report["note"]}


# ---------------------------------------------------------------- Genetic Algorithm
@protected.post("/api/v1/optimize")
def optimize(body: OptimizeBody):
    profile = profile_for(body.junction, body.period)
    observed = [profile["pcu_vph_by_direction"][d] * body.multiplier for d in pp.DIRECTIONS]
    predicted = [v * body.multiplier for v in predicted_demand(profile)] if body.source == "predicted" else None
    if body.source == "manual":
        if not body.manual_vph or len(body.manual_vph) != 4 or min(body.manual_vph) < 0:
            raise HTTPException(status_code=400, detail="Provide 4 non-negative manual demand values (vehicles/hour).")
        demand = [v * profile["pcu_per_vehicle"][d] for v, d in zip(body.manual_vph, pp.DIRECTIONS)]
        label = "HYPOTHETICAL: manually entered vehicles/hour converted to PCU/h"
    else:
        demand = predicted or observed
        label = ("XGBoost-predicted demand from the observed clips of this period" if predicted else "Observed demand of this period") + f" x demand multiplier {body.multiplier}"
    cfg = sm.Config(cycle_length=body.cycle_length, min_green=body.min_green, max_green=body.max_green, lost_time=body.lost_time,
                    saturation_flow=body.saturation_flow, fixed_plan=body.fixed_plan)
    try:
        baseline = sm.fixed_plan_greens(cfg, profile_for(body.junction, "all"))
        result = ga.optimize(demand, cfg.cycle_length, cfg.min_green, cfg.max_green, cfg.lost_time, cfg.saturation_flow,
                             body.population_size, body.generations, seed=body.seed, baseline=baseline)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {**result, "kind": "simulated", "demand_source": label, "observed_pcu_h": observed, "predicted_pcu_h": predicted, "directions": pp.DIRECTIONS,
            "explanation": ga.explain(result, pp.DIRECTIONS), "profile": public(profile),
            "limitations": ["Delays use the HCM-style formula, they are not measured waiting times.", "Saturation flow, lost time and PCU weights are assumptions, not Pune measurements.",
                            "UP/DOWN/RIGHT/LEFT are treated as four separately-phased signal groups; the CSV does not describe the real layout.",
                            "The result is a recommendation for the model, not a deployed signal plan."]}


# ---------------------------------------------------------------- experiments: Fixed-Time vs Adaptive
@protected.post("/api/v1/experiments")
def run_experiment(body: ExperimentBody):
    profile, overall, cfg = run_config(body)
    models, report = get_models()
    try:
        result = sm.compare(profile, overall, cfg, models[ml.CONTROL_HORIZON], report["junction_codes"][body.junction], body.n_seeds, body.base_seed)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    period = next((p["label"] for p in analysis.list_periods(get_data()["clips"], body.junction) if p["id"] == body.period), body.period)
    scenario, group = f"{body.junction} - {period.split(':')[0]}", uuid.uuid4().hex[:8]
    name = body.name.strip() or f"{body.junction.replace('Chowk', '')} {body.period} x{body.multiplier}"
    ids = [_record("experiment", scenario, _saved_shape(name, ctrl, body, profile, result["summary"][ctrl],
                                                        {"group": group, "n_seeds": body.n_seeds, "base_seed": body.base_seed, "reduction": result["reduction"],
                                                         "fixed_greens": result["fixed_greens"], "plans": result["examples"][ctrl]["plans"]})) for ctrl in ("fixed", "adaptive")]
    return {"kind": "simulated", "note": AUTO_NOTE, "name": name, "scenario": scenario, "multiplier": body.multiplier, "group": group, "saved_ids": ids, "profile": public(profile),
            "directions": pp.DIRECTIONS, **result}


@protected.get("/api/v1/dashboard/simulated")
def dashboard_simulated():
    """A default Fixed-vs-Adaptive comparison (busiest-covered junction, all sampled clips), computed once per server run, not saved."""
    if "default_compare" not in _cache:
        junction = max(get_data()["report"]["clips_per_junction"].items(), key=lambda kv: kv[1])[0]
        body = ExperimentBody(junction=junction)
        profile, overall, cfg = run_config(body)
        models, report = get_models()
        result = sm.compare(profile, overall, cfg, models[ml.CONTROL_HORIZON], report["junction_codes"][junction], body.n_seeds)
        _cache["default_compare"] = {"kind": "simulated", "note": AUTO_NOTE, "junction": junction, "period": "all", "duration_s": cfg.duration,
                                     "n_seeds": body.n_seeds, "summary": result["summary"], "reduction": result["reduction"]}
    return _cache["default_compare"]


@protected.get("/api/v1/history")
def history(limit: int = Query(100, ge=1, le=500)):
    return {"items": db.list_runs(None, limit)}


@protected.get("/api/v1/history/{run_id}")
def history_item(run_id: int):
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Experiment {run_id} not found.")
    return run


@protected.delete("/api/v1/history")
def clear_history():
    return {"deleted": db.clear_runs()}


# ---------------------------------------------------------------- live simulation (REST control + WebSocket stream)
def _current_sim() -> sm.Simulation:
    if _sim["sim"] is None:
        raise HTTPException(status_code=409, detail="No simulation yet. Start one first.")
    return _sim["sim"]


def _state() -> dict:
    return {**_current_sim().snapshot(), "kind": "simulated", "meta": _sim["meta"]}


@protected.post("/api/v1/simulation/start")
def simulation_start(body: StartBody):
    profile, overall, cfg = run_config(body)
    model, code = None, 0
    if body.controller == "adaptive":
        models, report = get_models()
        model, code = models[ml.CONTROL_HORIZON], report["junction_codes"][body.junction]
    try:
        sim = sm.Simulation(profile, body.controller, body.seed, cfg, sm.fixed_plan_greens(cfg, overall), model, code)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    sim.running = True
    _sim["sim"], _sim["meta"] = sim, {"junction": body.junction, "period": body.period, "scenario": f"{body.junction} - {body.period}",
                                      "demand_pcu_h": profile["pcu_vph_by_direction"], "directions": pp.DIRECTIONS}
    return _state()


@protected.post("/api/v1/simulation/step")
def simulation_step(body: StepBody):
    _advance(_current_sim(), body.seconds)
    return _state()


@protected.post("/api/v1/simulation/pause")
def simulation_pause():
    _current_sim().running = False
    return _state()


@protected.post("/api/v1/simulation/resume")
def simulation_resume():
    sim = _current_sim()
    sim.running = sim.t < sim.cfg.duration
    return _state()


@protected.post("/api/v1/simulation/reset")
def simulation_reset():
    _current_sim().reset()
    return _state()


@protected.get("/api/v1/simulation/state")
def simulation_state():
    return _state()


@app.websocket("/ws/simulation")
async def simulation_stream(websocket: WebSocket, token: str | None = Query(default=None)):
    """Sends the simulation state once per second and advances a running simulation by `speed` simulated seconds per tick.
    The client changes the speed with {"speed": 60}; start/pause/resume/reset use REST."""
    await websocket.accept()
    if auth.verify_token(token or "") is None:
        await websocket.close(code=4401)  # 4401 = not signed in; the frontend then shows the login page
        return
    speed = {"value": 30}

    async def listen():
        while True:
            message = await websocket.receive_json()
            speed["value"] = max(1, min(600, int(message.get("speed", speed["value"]))))

    listener = asyncio.create_task(listen())
    try:
        while not listener.done():
            if _sim["sim"] is None:
                await websocket.send_json({"idle": True})
            else:
                await asyncio.to_thread(_advance, _sim["sim"], speed["value"])
                await websocket.send_json(_state())
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    finally:
        listener.cancel()


app.include_router(protected)  # must come after every @protected route above
