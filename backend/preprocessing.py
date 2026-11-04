"""Load, validate and preprocess the Pune traffic CSV. The original CSV is never modified.

Source: "Heterogeneous Traffic Count Dataset, Pune (Jan 2023)" (Mendeley Data, see SOURCE below). The project uses
100,000 SELECTED records of it. Columns: Date, Time, Direction, car, motorbike, bus, truck, Junction, Camera, SourceFile.
What the file really contains (verified by `clean()` / `quality_report()` and shown in the data-quality report):
  * 115 source files (one per camera and day) from 3 junctions, ~8-9 s of rows each, ~25 rows per `Time` value.
  * Inside every file/direction the class columns NEVER decrease (checked on all series). Because of that, the vehicles of a
    file are `last value - first value` and per-second arrivals are differences; adding up the rows would count the same
    vehicle many times. The count values themselves are never changed.
  * `Date` is derived from the source filename (a2_11 -> 2023-01-11). Re-run `python -m backend.preprocessing` to rebuild data/processed/*.
"""
import json
import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = Path(os.getenv("TRAFFIC_AI_DATA") or ROOT / "data" / "raw" / "Pune_Traffic_100000_records_with_metadata.csv")
OUT_DIR = ROOT / "data" / "processed"
EXPECTED_ROWS = 100_000
CLASSES = ["car", "motorbike", "bus", "truck"]
DIRECTIONS = ["UP", "DOWN", "RIGHT", "LEFT"]
REQUIRED = ["Date", "Time", "Direction", *CLASSES, "Junction", "Camera", "SourceFile"]
SOURCE = {"name": "Heterogeneous Traffic Count Dataset, Pune (Jan 2023)", "publisher": "Mendeley Data", "doi": "10.17632/xnf2k6n288.1",
          "url": "https://data.mendeley.com/datasets/xnf2k6n288/1", "contributors": "Ashwini Matange and Jibi Abraham",
          "license": "CC BY 4.0", "collection_period": "January 11-18, 2023", "selected_records": 100_000,
          "subset_note": "This project uses 100,000 selected records of the original dataset, not the complete dataset."}
KEY = ["Junction", "SourceFile", "Direction"]
# Passenger-car units (ASSUMPTION, typical urban-India values in the spirit of IRC:106; editable): used to turn vehicle
# counts into road-space demand for the signal model.
PCU = {"car": 1.0, "motorbike": 0.5, "bus": 3.7, "truck": 3.7}


def load_raw(path=RAW_PATH) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}. Put the Pune CSV in data/raw/.")
    df = pd.read_csv(path, encoding="utf-8-sig")  # utf-8-sig removes the byte-order mark in front of "Time"
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")
    return df


def estimate_fps(df: pd.DataFrame) -> int:
    """Frames per second = typical number of rows one direction has inside one clock-second of one clip."""
    return int(df.groupby(["SourceFile", "Time", "Direction"]).size().median())


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Validate every row. Invalid rows are dropped and counted, nothing is imputed or invented."""
    df = df[REQUIRED].copy()
    report = {"rows_in": len(df), "missing_values": int(df.isna().sum().sum())}
    df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d", errors="coerce")
    df["t_s"] = pd.to_timedelta(df["Time"].astype(str), errors="coerce").dt.total_seconds()  # seconds since midnight
    df["Direction"] = df["Direction"].astype(str).str.strip().str.upper()
    counts = df[CLASSES].apply(pd.to_numeric, errors="coerce")
    bad = {
        "bad_date": df["Date"].isna(),
        "bad_time": df["t_s"].isna(),
        "bad_direction": ~df["Direction"].isin(DIRECTIONS),
        "bad_count": counts.isna().any(axis=1) | (counts < 0).any(axis=1) | (counts % 1 != 0).any(axis=1),
        "missing_junction_or_file": df[["Junction", "Camera", "SourceFile"]].isna().any(axis=1),
    }
    report["invalid_rows"] = {name: int(mask.sum()) for name, mask in bad.items()}
    keep = ~pd.concat(bad, axis=1).any(axis=1)
    df = df[keep].copy()
    df[CLASSES] = counts[keep].astype(int)
    df["frame"] = df.groupby(["SourceFile", "Direction"]).cumcount()  # row order inside a clip = frame order
    report["rows_valid"] = len(df)
    report["matches_expected_100000"] = len(df) == EXPECTED_ROWS and report["rows_in"] == EXPECTED_ROWS
    return df, report


def increments(df: pd.DataFrame) -> pd.DataFrame:
    """Rise of every class counter from one row to the next INSIDE one (junction, file, direction) sequence, never across
    sequences. The first row of a sequence gives 0 (vehicles already counted there are not arrivals). If a counter ever
    decreases it is treated as a reset to 0, so the new value counts as new vehicles. Stored values are not changed."""
    previous = df.groupby(KEY)[CLASSES].shift()
    rise = df[CLASSES] - previous
    return rise.where(rise >= 0, df[CLASSES]).where(previous.notna(), 0).astype(int)


def _meta(df: pd.DataFrame) -> pd.DataFrame:
    """Date (text) and Camera of every source file, so processed tables keep the observation identity."""
    return df.groupby("SourceFile").agg(Date=("Date", lambda d: d.iloc[0].strftime("%Y-%m-%d")), Camera=("Camera", "first"))


def build_clips(df: pd.DataFrame, fps: int) -> pd.DataFrame:
    """One row per (junction, file, direction): Date, Camera, clip start, duration and vehicles counted per class."""
    g = df.groupby(KEY)
    clips = g.agg(start_s=("t_s", "min"), frames=("frame", "size")).reset_index().join(_meta(df), on="SourceFile")
    totals = increments(df).join(df[KEY]).groupby(KEY)[CLASSES].sum().reset_index()
    clips = clips.merge(totals, on=KEY)                   # vehicles = sum of counter increases inside the sequence
    clips["carried_in"] = g[CLASSES].first().sum(axis=1).values   # already counted in the first row (not arrivals)
    clips["duration_s"] = clips["frames"] / fps
    clips["vehicles"] = clips[CLASSES].sum(axis=1)
    return clips[["Date", "Camera", "Junction", "SourceFile", "Direction", "start_s", "frames", *CLASSES, "carried_in", "duration_s", "vehicles"]]


def build_arrivals(df: pd.DataFrame, fps: int) -> pd.DataFrame:
    """Vehicles that arrived in each full 1-second bin (`fps` rows) of each file and direction, per class."""
    rows = df[KEY + ["frame"]].join(increments(df))
    rows["sec"] = rows["frame"] // fps
    bins = rows.groupby(KEY + ["sec"]).agg(n=("frame", "size"), **{c: (c, "sum") for c in CLASSES}).reset_index()
    out = bins[bins["n"] == fps].drop(columns="n")        # a partial last bin would under-count, so it is left out
    out = out.join(df.groupby("SourceFile")["t_s"].min().rename("start_s"), on="SourceFile").join(_meta(df), on="SourceFile")
    return out.sort_values(["start_s", "SourceFile", "Direction", "sec"]).reset_index(drop=True)


def g_first(df):
    """Sum of the first-row counters of every (file, direction) sequence."""
    return df.groupby(["SourceFile", "Direction"])[CLASSES].first().sum(axis=1)


def quality_report(df: pd.DataFrame, report: dict, clips: pd.DataFrame, fps: int) -> dict:
    """Facts about the data, all computed from the CSV, plus the limitations a reader must know."""
    series = df.groupby(["SourceFile", "Direction"])[CLASSES]
    decreasing = sum(int((s.diff().dropna() < 0).any().sum()) for _, s in series)
    hhmm = lambda s: f"{int(s // 3600):02d}:{int(s % 3600 // 60):02d}:{int(s % 60):02d}"  # noqa: E731
    one_date = bool((df.groupby("SourceFile")["Date"].nunique() == 1).all())
    one_identity = bool((df.groupby("SourceFile")[["Camera", "Junction"]].nunique() == 1).all().all())
    seq = df.groupby(["SourceFile", "Direction"])["t_s"]
    clip_s = clips.groupby("SourceFile")["duration_s"].max()
    report.update(
        source=SOURCE,
        exact_duplicate_rows=int(df[REQUIRED].duplicated().sum()),
        junctions=sorted(df["Junction"].unique().tolist()),
        cameras=sorted(df["Camera"].unique().tolist()),
        clips=int(df["SourceFile"].nunique()),
        rows_per_junction=df["Junction"].value_counts().sort_index().to_dict(),
        clips_per_junction=df.groupby("Junction")["SourceFile"].nunique().to_dict(),
        rows_per_direction=df["Direction"].value_counts().to_dict(),
        directions=sorted(df["Direction"].unique().tolist()),
        estimated_fps=fps,
        counter_series=int(len(series)) * len(CLASSES),
        counters_that_decrease=decreasing,
        clips_with_nonzero_first_frame=int(clips.loc[clips["carried_in"] > 0, "SourceFile"].nunique()),
        first_date=df["Date"].min().strftime("%Y-%m-%d"), last_date=df["Date"].max().strftime("%Y-%m-%d"),
        dates=int(df["Date"].nunique()), one_date_per_file=one_date, one_camera_junction_per_file=one_identity,
        time_never_goes_back=bool((seq.diff().dropna() >= 0).all()),
        clip_seconds={"min": round(float(clip_s.min()), 2), "mean": round(float(clip_s.mean()), 2), "max": round(float(clip_s.max()), 2)},
        counter_first_value_zero=int((g_first(df) == 0).sum()), counter_sequences=int(len(series)),
        date_matches_filename=bool((df["SourceFile"].str.extract(r"_(\d+)")[0].astype(int) == df["Date"].dt.day).all()),
        camera_matches_filename=bool((df["SourceFile"].str.split("_").str[0] == df["Camera"]).all()),
        first_time=hhmm(df["t_s"].min()), last_time=hhmm(df["t_s"].max()),
        total_clip_seconds=round(float(clips.groupby("SourceFile")["duration_s"].max().sum()), 1),
        total_vehicles=int(clips["vehicles"].sum()),
        vehicles_by_class={c: int(clips[c].sum()) for c in CLASSES},
    )
    report["notes"] = {  # not warnings: how the verified facts above are used
        "count_handling": f"Count values are stored unchanged. Every counter only rises inside its file and direction ({decreasing} of {report['counter_series']} "
                          "series decrease), so vehicles are the sum of increases within one file/direction, never summed rows or differences across files.",
        "duplicates": "Identical rows are repeated video frames of the same second and are kept.",
    }
    report["limitations"] = [{"title": "Limited Junction Coverage",
                              "text": "The dataset covers only three traffic junctions in Pune. Model performance may vary when applied to other junctions."}]
    return report


def run_preprocessing(raw_path=RAW_PATH, out_dir=OUT_DIR) -> dict:
    """Full pipeline: load -> validate -> clips + 1-second arrivals -> data/processed/. Safe to re-run."""
    df, report = clean(load_raw(raw_path))
    fps = estimate_fps(df)
    clips, arrivals = build_clips(df, fps), build_arrivals(df, fps)
    report = quality_report(df, report, clips, fps)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    clips.to_csv(out_dir / "clips.csv", index=False)
    arrivals.to_csv(out_dir / "arrivals_1s.csv", index=False)
    (out_dir / "data_quality_report.json").write_text(json.dumps(report, indent=2))
    return {"report": report, "clips": clips, "arrivals": arrivals}


if __name__ == "__main__":
    print(json.dumps(run_preprocessing()["report"], indent=2))
