import numpy as np

from backend import model as ml
from backend import preprocessing as pp


def test_features_at_second_t_never_use_later_seconds():
    rng = np.random.default_rng(0)
    arr = rng.integers(0, 3, size=(8, 4, 4)).astype(float)
    changed = arr.copy()
    changed[5:] += 7                                   # change only seconds 5..7
    a, b = ml.window_features(arr, 0), ml.window_features(changed, 0)
    assert a[a["t"] <= 4][ml.FEATURES].equals(b[b["t"] <= 4][ml.FEATURES])
    assert not a[a["t"] >= 5][ml.FEATURES].equals(b[b["t"] >= 5][ml.FEATURES])


def test_target_is_arrivals_in_the_next_h_seconds(pipeline):
    s = ml.build_samples(pipeline["arrivals"])
    clip = s[(s["SourceFile"] == s["SourceFile"].iloc[0]) & (s["direction"] == 0)].sort_values("t")
    a_t = clip["a_t"].values
    assert np.allclose(clip["y2"].values[:-2], a_t[1:-1] + a_t[2:])  # y2 at t = arrivals at t+1 and t+2


def test_split_is_chronological_by_clip_with_no_clip_in_two_parts(pipeline):
    s = ml.build_samples(pipeline["arrivals"])
    start = s.groupby("split")["start_s"].agg(["min", "max"])
    assert start.loc["train", "max"] <= start.loc["val", "min"] <= start.loc["val", "max"] <= start.loc["test", "min"]
    assert s.groupby("SourceFile")["split"].nunique().max() == 1


def test_training_reports_honest_metrics_for_models_and_baselines(trained):
    models, report = trained
    assert sorted(models) == list(ml.HORIZONS) and report["features"] == ml.FEATURES
    for names in report["metrics"].values():
        assert {"XGBoost", "Random Forest", "Linear Regression", "Baseline: historical mean", "Baseline: recent rate"} == set(names)
        assert all(m["test"]["mae"] >= 0 and m["test"]["rmse"] >= m["test"]["mae"] for m in names.values())


def test_predictions_are_non_negative_and_come_from_unseen_clips(trained, pipeline):
    models, _ = trained
    samples = ml.build_samples(pipeline["arrivals"])
    out = ml.split_predictions(models, samples, 3)
    assert (out["predicted"] >= 0).all() and set(out["split"]) == {"test"}
    rate = ml.demand_rate(models[3], np.ones((20, 4, 4)), junction_code=0)
    assert rate.shape == (4,) and (rate >= 0).all()
