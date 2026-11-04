"""Short-term demand prediction: how many vehicles will arrive in the NEXT H seconds in each direction of a junction.

Why this target: the Pune CSV holds cumulative counters of short video clips, not hourly volumes, so the only forecastable
quantity is the arrival count of the next few seconds. It is a noisy, mostly-zero count, so expect low R² - the report
says so honestly and compares XGBoost with two simple baselines and with Linear Regression / Random Forest.

No leakage:
  * features at second t use only seconds <= t of the same clip (see `window_features`);
  * train / validation / test are separated by CLIP (never inside a clip), in order of clip start time (70% / 15% / 15%).
    The validation part is only used for XGBoost early stopping; the test part is never used for any decision.
Run `python -m backend.model` to train, evaluate and save models/.
"""
import json
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from backend import preprocessing as pp

MODEL_PATH = pp.ROOT / "models" / "xgb_models.joblib"
REPORT_PATH = pp.ROOT / "models" / "model_report.json"
HORIZONS, CONTROL_HORIZON = (1, 2, 3, 4), 3  # seconds ahead; the Adaptive controller uses CONTROL_HORIZON
FEATURES = ["junction", "direction", "a_t", "a_t1", "a_t2", "sum3", "others", *pp.CLASSES]
# a_t, a_t1, a_t2 = vehicles that arrived in the current / previous / second-previous second; sum3 = their sum;
# others = arrivals in the other three directions now; car..truck = this second's arrivals by vehicle category.


class ModelNotFoundError(FileNotFoundError):
    """Raised when the model has not been trained yet."""


def clip_arrays(arrivals: pd.DataFrame) -> dict:
    """{clip: (junction, start_s, array[T seconds, 4 directions, 4 classes])} from the 1-second arrival table."""
    out = {}
    for name, g in arrivals.groupby("SourceFile"):
        T = int(g.groupby("Direction")["sec"].count().min())
        arr = np.zeros((T, len(pp.DIRECTIONS), len(pp.CLASSES)))
        for i, d in enumerate(pp.DIRECTIONS):
            arr[:, i, :] = g[g["Direction"] == d].sort_values("sec").head(T)[pp.CLASSES].values
        out[name] = (g["Junction"].iloc[0], float(g["start_s"].iloc[0]), arr)
    return out


def window_features(arr: np.ndarray, junction_code: int) -> pd.DataFrame:
    """Features for every second t of `arr` (T, 4, 4) using only seconds <= t. Rows are ordered by t, then direction.
    Missing history before the start of the window counts as 0 arrivals."""
    T = len(arr)
    tot = arr.sum(axis=2)
    back = lambda k: np.vstack([np.zeros((k, 4)), tot])[:T]  # noqa: E731  arrivals k seconds earlier
    a0, a1, a2 = tot, back(1), back(2)
    cols = {"junction": np.full(T * 4, junction_code), "direction": np.tile(np.arange(4), T), "t": np.repeat(np.arange(T), 4),
            "a_t": a0.ravel(), "a_t1": a1.ravel(), "a_t2": a2.ravel(), "sum3": (a0 + a1 + a2).ravel(),
            "others": (tot.sum(axis=1, keepdims=True) - tot).ravel()}
    cols.update({c: arr[:, :, i].ravel() for i, c in enumerate(pp.CLASSES)})
    return pd.DataFrame(cols)


def junction_codes(arrivals: pd.DataFrame) -> dict:
    return {j: i for i, j in enumerate(sorted(arrivals["Junction"].unique()))}


def build_samples(arrivals: pd.DataFrame) -> pd.DataFrame:
    """One row per (clip, second, direction) with features, the targets y1..y4 (arrivals in the next H seconds) and a split label."""
    codes, parts = junction_codes(arrivals), []
    for name, (junction, start_s, arr) in clip_arrays(arrivals).items():
        df, T = window_features(arr, codes[junction]), len(arr)
        cum = np.vstack([np.zeros((1, 4)), arr.sum(axis=2).cumsum(axis=0)])  # cum[k] = arrivals in the first k seconds
        for h in HORIZONS:
            y = np.full((T, 4), np.nan)
            if T > h:
                y[: T - h] = cum[h + 1: T + 1] - cum[1: T - h + 1]  # arrivals in seconds t+1 .. t+h
            df[f"y{h}"] = y.ravel()
        df["recent_rate"] = df["sum3"] / np.minimum(df["t"] + 1, 3)  # baseline input: mean arrivals per second, last <=3 s
        parts.append(df.assign(SourceFile=name, Junction=junction, start_s=start_s))
    samples = pd.concat(parts, ignore_index=True)
    order = samples.groupby("SourceFile")["start_s"].first().reset_index().sort_values(["start_s", "SourceFile"])["SourceFile"].tolist()
    a, b = int(len(order) * 0.70), int(len(order) * 0.85)
    label = {**dict.fromkeys(order[:a], "train"), **dict.fromkeys(order[a:b], "val"), **dict.fromkeys(order[b:], "test")}
    samples["split"] = samples["SourceFile"].map(label)
    return samples


def make_models() -> dict:
    from xgboost import XGBRegressor
    linear = Pipeline([("prep", ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore"), ["junction", "direction"])],
                                                  remainder="passthrough")), ("model", LinearRegression())])
    return {"Linear Regression": linear,
            "Random Forest": RandomForestRegressor(n_estimators=150, min_samples_leaf=5, random_state=42, n_jobs=1),
            "XGBoost": XGBRegressor(n_estimators=300, learning_rate=0.05, max_depth=3, subsample=0.8, colsample_bytree=0.8,
                                    early_stopping_rounds=30, random_state=42, n_jobs=1)}


def score(actual, predicted) -> dict:
    return {"mae": float(mean_absolute_error(actual, predicted)), "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
            "r2": float(r2_score(actual, predicted)) if len(actual) > 1 and np.var(actual) > 0 else None}


def train_and_save(arrivals: pd.DataFrame | None = None) -> dict:
    arrivals = pp.run_preprocessing()["arrivals"] if arrivals is None else arrivals
    samples = build_samples(arrivals)
    metrics, xgb_models, split_info = {}, {}, {}
    for h in HORIZONS:
        y = f"y{h}"
        data = samples.dropna(subset=[y])
        tr, va, te = (data[data["split"] == s] for s in ("train", "val", "test"))
        mean = tr.groupby(["junction", "direction"])[y].mean()
        predictors = {}
        for name, est in make_models().items():
            est.fit(tr[FEATURES], tr[y], **({"eval_set": [(va[FEATURES], va[y])], "verbose": False} if name == "XGBoost" else {}))
            predictors[name] = lambda df, est=est: np.clip(est.predict(df[FEATURES]), 0, None)
            if name == "XGBoost":
                xgb_models[h] = est
        predictors["Baseline: historical mean"] = lambda df: mean.reindex(pd.MultiIndex.from_frame(df[["junction", "direction"]])).fillna(tr[y].mean()).values
        predictors["Baseline: recent rate"] = lambda df: h * df["recent_rate"].values
        metrics[str(h)] = {name: {"val": score(va[y], fn(va)), "test": score(te[y], fn(te))} for name, fn in predictors.items()}
        split_info[str(h)] = {s: {"rows": len(d), "clips": int(d["SourceFile"].nunique()), "mean_target": float(d[y].mean()),
                                  "start_range_s": [float(d["start_s"].min()), float(d["start_s"].max())]} for s, d in zip(("train", "val", "test"), (tr, va, te))}
    report = {"trained_at": datetime.now().isoformat(timespec="seconds"), "features": FEATURES, "horizons": list(HORIZONS),
              "control_horizon": CONTROL_HORIZON, "junction_codes": junction_codes(arrivals), "metrics": metrics, "split": split_info,
              "target": "vehicles arriving in the next H seconds, one direction of one junction",
              "split_method": "chronological by clip start time, 70% train / 15% validation (XGBoost early stopping only) / 15% test",
              "note": "Counts of a few seconds are mostly zero, so R² is low for every model. Test metrics are on clips never used for training."}
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(xgb_models, MODEL_PATH)
    REPORT_PATH.write_text(json.dumps(report, indent=2))
    return report


def load_model() -> tuple[dict, dict]:
    """(models by horizon, report). Raises ModelNotFoundError if training has not been run or the features changed."""
    if not MODEL_PATH.exists() or not REPORT_PATH.exists():
        raise ModelNotFoundError("Model not trained yet. Run: python -m backend.model")
    report = json.loads(REPORT_PATH.read_text())
    if report.get("features") != FEATURES:
        raise ModelNotFoundError("The saved model uses different features. Retrain with: python -m backend.model")
    return joblib.load(MODEL_PATH), report


def split_predictions(models: dict, samples: pd.DataFrame, horizon: int, split: str = "test") -> pd.DataFrame:
    """Actual vs predicted arrivals for the held-out clips (rows the model never saw in training)."""
    data = samples[(samples["split"] == split)].dropna(subset=[f"y{horizon}"])
    return data.assign(actual=data[f"y{horizon}"], predicted=np.clip(models[horizon].predict(data[FEATURES]), 0, None))


def demand_rate(model, history: np.ndarray, junction_code: int, horizon: int = CONTROL_HORIZON) -> np.ndarray:
    """Predicted arrival rate (vehicles/second) per direction: the mean model output over every second of `history`
    (T, 4, 4), each output being a forecast for the following `horizon` seconds. Needs at least 3 seconds."""
    f = window_features(history, junction_code)
    f = f[f["t"] >= 2]  # the first two seconds have incomplete lags
    return np.clip(model.predict(f[FEATURES]), 0, None).reshape(-1, 4).mean(axis=0) / horizon


if __name__ == "__main__":
    print(json.dumps(train_and_save(), indent=2)[:3000])
