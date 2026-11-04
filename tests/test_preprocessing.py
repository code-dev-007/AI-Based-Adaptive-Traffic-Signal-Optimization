import hashlib

import numpy as np
import pandas as pd
import pytest

from backend import preprocessing as pp


def test_real_dataset_has_exactly_100000_valid_rows(pipeline):
    r = pipeline["report"]
    assert r["rows_in"] == 100_000 and r["rows_valid"] == 100_000 and r["matches_expected_100000"]
    assert r["missing_values"] == 0 and sum(r["invalid_rows"].values()) == 0
    assert r["junctions"] == ["AlankarChowk", "JehangirChowk", "RTOChowk"] and r["first_date"] == "2023-01-11" and r["last_date"] == "2023-01-18" and r["source"]["doi"] == "10.17632/xnf2k6n288.1"


def test_counters_are_cumulative_so_clip_vehicles_are_last_minus_first(pipeline):
    df, _ = pp.clean(pp.load_raw())
    assert pipeline["report"]["counters_that_decrease"] == 0
    expected = (df.groupby(pp.KEY)[pp.CLASSES].last() - df.groupby(pp.KEY)[pp.CLASSES].first()).sum().sum()
    assert pipeline["clips"]["vehicles"].sum() == expected == pipeline["report"]["total_vehicles"]
    assert expected < len(df)  # summing the rows would count each vehicle many times


def test_arrivals_are_non_negative_and_never_exceed_clip_totals(pipeline):
    a, c = pipeline["arrivals"], pipeline["clips"]
    assert (a[pp.CLASSES] >= 0).all().all()
    per_clip = a.groupby(pp.KEY)[pp.CLASSES].sum().sum(axis=1)
    totals = c.set_index(pp.KEY)["vehicles"].reindex(per_clip.index)
    assert (per_clip <= totals + 1e-9).all()


def test_invalid_rows_are_dropped_and_counted_not_repaired():
    D = "2023-01-11"
    rows = [(D, "09:00:00", "UP", 1, 0, 0, 0, "J", "a2", "a2_11.csv"), (D, "bad", "UP", 1, 0, 0, 0, "J", "a2", "a2_11.csv"),
            (D, "09:00:01", "SIDE", 1, 0, 0, 0, "J", "a2", "a2_11.csv"), (D, "09:00:02", "UP", -1, 0, 0, 0, "J", "a2", "a2_11.csv"),
            (D, "09:00:03", "DOWN", 2, 0, 0, 0, "J", "a2", "a2_11.csv"), ("not-a-date", "09:00:04", "UP", 1, 0, 0, 0, "J", "a2", "a2_11.csv")]
    df, report = pp.clean(pd.DataFrame(rows, columns=pp.REQUIRED))
    assert len(df) == 2 and report["invalid_rows"] == {"bad_date": 1, "bad_time": 1, "bad_direction": 1, "bad_count": 1, "missing_junction_or_file": 0}
    assert not report["matches_expected_100000"]


def test_missing_file_and_missing_columns_give_clear_errors(tmp_path):
    with pytest.raises(FileNotFoundError):
        pp.load_raw(tmp_path / "nope.csv")
    (tmp_path / "bad.csv").write_text("Time,Direction\n09:00:00,UP\n")
    with pytest.raises(ValueError, match="missing required columns"):
        pp.load_raw(tmp_path / "bad.csv")


def test_pipeline_can_be_rerun_and_never_modifies_the_original_csv(tmp_path):
    digest = lambda: hashlib.sha256(pp.RAW_PATH.read_bytes()).hexdigest()  # noqa: E731
    before = digest()
    first = pp.run_preprocessing(out_dir=tmp_path)["clips"]
    second = pp.run_preprocessing(out_dir=tmp_path)["clips"]
    assert digest() == before and first.equals(second)
    assert {"clips.csv", "arrivals_1s.csv", "data_quality_report.json"} <= {p.name for p in tmp_path.iterdir()}


def test_increments_stay_inside_a_sequence_and_handle_resets():
    row = lambda f, d, car: {"Junction": "J", "SourceFile": f, "Direction": d, "car": car, "motorbike": 0, "bus": 0, "truck": 0}  # noqa: E731
    df = pd.DataFrame([row("a", "UP", 5), row("a", "UP", 7), row("a", "UP", 2), row("a", "DOWN", 9), row("b", "UP", 100), row("b", "UP", 101)])
    # first row of every (file, direction) sequence is 0; 5->7 is +2; 7->2 is a reset, so 2 new vehicles; nothing crosses sequences
    assert pp.increments(df)["car"].tolist() == [0, 2, 2, 0, 0, 1]


def test_dates_survive_preprocessing_and_dates_are_not_merged(pipeline):
    clips, arrivals = pipeline["clips"], pipeline["arrivals"]
    assert {"Date", "Camera", "Junction", "SourceFile"} <= set(clips.columns) and {"Date", "Camera"} <= set(arrivals.columns)
    assert clips["Date"].nunique() == 8 and clips.groupby("SourceFile")["Date"].nunique().max() == 1
    assert clips["SourceFile"].nunique() == 115 and clips["vehicles"].sum() == 760
