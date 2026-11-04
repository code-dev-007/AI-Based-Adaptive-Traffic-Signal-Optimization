"""Peak-period analysis and observed demand profiles, computed from the per-clip table (backend.preprocessing).

The selected records hold only a few short clips per minute, so "peak" is discovered from the data
per junction instead of being assumed. A clock minute is summarised by its traffic rate:
    rate (vehicles/hour-equivalent) = vehicles counted / seconds of video sampled x 3600
and labelled relative to that junction's own average rate:
    heavy (peak)  : rate >= HEAVY_RATIO x average     light (off-peak): rate <= LIGHT_RATIO x average
    insufficient  : fewer than MIN_CLIPS clips in that minute (too little video to trust the rate)
"""
import re

import pandas as pd

from backend.preprocessing import CLASSES, DIRECTIONS, PCU

MIN_CLIPS, HEAVY_RATIO, LIGHT_RATIO, MIN_WINDOW_S = 3, 1.25, 0.75, 15
METHOD = (f"Observed vehicle counts come from the recorded video clips (each identified by Date, Camera and SourceFile). An estimated rate is "
          f"vehicles / sampled video seconds x 3600, so it extrapolates a few seconds of video to one hour. Per-minute views are aggregated "
          f"across the selected dates: a clock minute is 'heavy' (peak) when its estimated rate is at least {HEAVY_RATIO}x that junction's average, "
          f"'light' (off-peak) when at most {LIGHT_RATIO}x, otherwise 'moderate'; minutes with fewer than {MIN_CLIPS} clips are 'insufficient'. "
          f"Date-wise windows are never mixed across dates; a date-window needs at least {MIN_WINDOW_S} s of video to be ranked.")
LIMITS = [{"title": "Limited Observation Coverage", "text": "Traffic observations are available only for recorded video intervals. Continuous 24-hour traffic patterns cannot be inferred from this dataset."},
          {"title": "Short Observation Duration", "text": "Traffic rates estimated from limited video samples may vary and should not be treated as actual hourly traffic counts."},
          {"title": "Observed Peak Window", "text": "The busiest period represents the highest traffic observed in available video samples, not the actual daily or city-wide rush hour."},
          {"title": "Count Basis", "text": "The dataset documentation describes per-interval counts, but every counter in the selected CSV only rises inside its file, so vehicles are the sum of increases per file and direction. Totals would differ if the counters mean something else."}]
hhmm = lambda minute: f"{minute // 60:02d}:{minute % 60:02d}"  # noqa: E731
hms = lambda s: f"{int(s // 3600):02d}:{int(s % 3600 // 60):02d}:{int(s % 60):02d}"  # noqa: E731


def with_pcu(clips: pd.DataFrame) -> pd.DataFrame:
    clips = clips.copy()
    clips["pcu"] = sum(clips[c] * PCU[c] for c in CLASSES)
    clips["minute"] = (clips.groupby("SourceFile")["start_s"].transform("min") // 60).astype(int)  # clip start minute
    clips["window"] = clips["minute"].map({m: w["id"] for w in split_windows(clips) for m in w["minutes"]})  # clock window A, B, ...
    return clips


def _rate(frame: pd.DataFrame, col="vehicles") -> float:
    """Vehicles per hour-equivalent for the selected clip rows (each row = one direction of one clip)."""
    seconds = frame["duration_s"].sum()
    return float(frame[col].sum() / seconds * 3600) if seconds else 0.0


def minute_levels(clips: pd.DataFrame) -> pd.DataFrame:
    """One row per (junction, clock minute) with its rate and heavy/light level. Rates are summed over the 4 directions."""
    rows = []
    for junction, jc in clips.groupby("Junction"):
        mean_rate = _rate(jc) * 4  # 4 directions sampled in parallel -> junction total
        for minute, mc in jc.groupby("minute"):
            rate = _rate(mc) * 4
            n = mc["SourceFile"].nunique()
            level = "insufficient" if n < MIN_CLIPS else "heavy" if rate >= HEAVY_RATIO * mean_rate else "light" if rate <= LIGHT_RATIO * mean_rate else "moderate"
            rows.append({"junction": junction, "minute": minute, "time": hhmm(minute), "hour": minute // 60, "clips": n, "dates": int(mc["Date"].nunique()),
                         "sampled_s": round(mc["duration_s"].sum() / 4, 1), "vehicles": int(mc["vehicles"].sum()),
                         "rate_vph": round(rate, 1), "pcu_vph": round(_rate(mc, "pcu") * 4, 1),
                         "intensity": round(rate / mean_rate, 2) if mean_rate else 0.0, "level": level,
                         "top_clip_pct": round(100 * mc.groupby("SourceFile")["vehicles"].sum().max() / max(mc["vehicles"].sum(), 1), 1)})
    return pd.DataFrame(rows)


def split_windows(clips: pd.DataFrame, gap_min=10) -> list[dict]:
    """Group clips into observation windows: a new window starts after a gap of >= gap_min minutes between clip starts."""
    minutes = sorted(clips["minute"].unique())
    windows, current = [], [minutes[0]]
    for m in minutes[1:]:
        if m - current[-1] >= gap_min:
            windows.append(current)
            current = []
        current.append(m)
    windows.append(current)
    return [{"id": chr(65 + i), "label": f"Window {chr(65 + i)} ({hhmm(w[0])}-{hhmm(w[-1])})", "minutes": w} for i, w in enumerate(windows)]


def _observation(frame: pd.DataFrame) -> dict:
    """Observed counts and the ESTIMATED hourly-equivalent rate of a set of clip rows (all directions)."""
    starts = frame.groupby("SourceFile")["start_s"].min()
    top = frame.groupby("SourceFile")["vehicles"].sum().max()
    return {"clips": int(frame["SourceFile"].nunique()), "cameras": sorted(frame["Camera"].unique()), "first_clip_start": hms(starts.min()), "last_clip_start": hms(starts.max()),
            "sampled_s": round(frame["duration_s"].sum() / 4, 1), "vehicles": int(frame["vehicles"].sum()), **{c: int(frame[c].sum()) for c in CLASSES},
            "rate_vph": round(_rate(frame) * 4, 1), "top_clip_pct": round(100 * top / max(frame["vehicles"].sum(), 1), 1)}


def date_analysis(clips: pd.DataFrame) -> dict:
    """Date-wise results. Every row is one (Date, junction[, window]); observations of different dates are never merged."""
    by_date, windows, busiest = [], [], []
    for (j, date), dc in clips.groupby(["Junction", "Date"]):
        by_date.append({"junction": j, "date": date, "weekday": pd.Timestamp(date).day_name(), **_observation(dc)})
    for (j, date, w), wc in clips.groupby(["Junction", "Date", "window"]):
        windows.append({"junction": j, "date": date, "window": w, **_observation(wc)})
    for j in sorted(clips["Junction"].unique()):
        ok = [r for r in windows if r["junction"] == j and r["sampled_s"] >= MIN_WINDOW_S]
        if ok:
            top = max(ok, key=lambda r: r["rate_vph"])
            busiest.append({**top, "weekday": pd.Timestamp(top["date"]).day_name(), "caution": bool(top["top_clip_pct"] >= 50)})
    return {"by_date": by_date, "date_windows": windows, "busiest_windows": busiest,
            "busiest_overall": max(busiest, key=lambda r: r["rate_vph"]) if busiest else None, "dates": sorted(clips["Date"].unique())}


def peak_analysis(clips: pd.DataFrame) -> dict:
    clips = with_pcu(clips)
    levels = minute_levels(clips)
    junctions = sorted(clips["Junction"].unique())
    by_junction, by_direction, windows, peak_vs_off, summary = [], [], [], [], []
    for j in junctions:
        jc = clips[clips["Junction"] == j]
        by_junction.append({"junction": j, "clips": int(jc["SourceFile"].nunique()), "sampled_s": round(jc["duration_s"].sum() / 4, 1),
                            "vehicles": int(jc["vehicles"].sum()), "rate_vph": round(_rate(jc) * 4, 1), "pcu_vph": round(_rate(jc, "pcu") * 4, 1),
                            **{c: int(jc[c].sum()) for c in CLASSES}})
        for d in DIRECTIONS:
            dc = jc[jc["Direction"] == d]
            by_direction.append({"junction": j, "direction": d, "vehicles": int(dc["vehicles"].sum()), "rate_vph": round(_rate(dc), 1),
                                 "share_pct": round(100 * dc["vehicles"].sum() / max(jc["vehicles"].sum(), 1), 1)})
        for w in split_windows(clips):
            wc = jc[jc["minute"].isin(w["minutes"])]
            if len(wc):
                windows.append({"junction": j, "window": w["label"], "dates": int(wc["Date"].nunique()), **_observation(wc)})
        lv = levels[(levels["junction"] == j) & (levels["level"] != "insufficient")]
        heavy, light = lv[lv["level"] == "heavy"], lv[lv["level"] == "light"]
        if lv.empty:
            continue
        top = lv.loc[lv["rate_vph"].idxmax()]
        row = {"junction": j, "busiest_minute": top["time"], "busiest_rate_vph": top["rate_vph"], "quietest_minute": lv.loc[lv["rate_vph"].idxmin(), "time"],
               "quietest_rate_vph": lv["rate_vph"].min(), "average_rate_vph": round(_rate(jc) * 4, 1)}
        mean_heavy = heavy["rate_vph"].mean() if len(heavy) else None
        mean_light = light["rate_vph"].mean() if len(light) else None
        row.update(peak_rate_vph=mean_heavy, offpeak_rate_vph=mean_light,
                   pct_difference=round(100 * (mean_heavy - mean_light) / mean_light, 1) if mean_heavy and mean_light else None)
        peak_vs_off.append(row)
        summary.append(f"{j}: busiest qualifying clock minute {top['time']} (all dates) at an estimated {top['rate_vph']:.0f} veh/h "
                       f"({top['intensity']:.2f}x its average) from {int(top['clips'])} clips ({top['sampled_s']:.0f} s of video)."
                       + (f" Caution: one clip holds {top['top_clip_pct']:.0f}% of that minute's vehicles." if top["top_clip_pct"] >= 50 else ""))
    hours = levels.groupby("hour").agg(clips=("clips", "sum"), vehicles=("vehicles", "sum"), sampled_s=("sampled_s", "sum")).reset_index()
    hours["rate_vph"] = (hours["vehicles"] / hours["sampled_s"] * 3600).round(1)
    full = pd.DataFrame({"hour": range(int(hours["hour"].min()), int(hours["hour"].max()) + 1)}).merge(hours, how="left")
    full["rate_vph"] = full["rate_vph"].astype(object).where(full["clips"].notna(), None)
    full["clips"] = full["clips"].fillna(0).astype(int)
    by_dir_minute = [{"junction": j, "direction": d, "time": hhmm(m), "clips": int(g["SourceFile"].nunique()), "rate_vph": round(_rate(g), 1)}
                     for (j, d, m), g in clips.groupby(["Junction", "Direction", "minute"])]
    by_minute_direction = [{"junction": j, "time": hhmm(m), "direction": d, "clips": g["SourceFile"].nunique(), "rate_vph": round(_rate(g), 1)}
                           for (j, m, d), g in clips.groupby(["Junction", "minute", "Direction"]) if g["SourceFile"].nunique() >= MIN_CLIPS]
    peaks = [r["busiest_minute"] for r in peak_vs_off]
    overall = {"time": max(set(peaks), key=peaks.count), "junctions": peaks.count(max(set(peaks), key=peaks.count)), "of": len(peaks)} if peaks else None
    return {**date_analysis(clips), "aggregation": "Aggregated across selected dates: by_minute, by_hour, by_direction, by_junction, windows, peak_vs_offpeak, summary",
            "total_sampled_s": round(clips["duration_s"].sum() / 4, 1), "total_vehicles": int(clips["vehicles"].sum()),
            "overall_peak": overall, "method": METHOD, "limitations": LIMITS, "thresholds": {"min_clips": MIN_CLIPS, "heavy": HEAVY_RATIO, "light": LIGHT_RATIO},
            "junctions": junctions, "by_minute": levels.to_dict("records"), "by_minute_direction": by_minute_direction, "by_direction_minute": by_dir_minute, "by_hour": full[["hour", "clips", "rate_vph"]].to_dict("records"),
            "by_junction": by_junction, "by_direction": by_direction, "windows": windows, "peak_vs_offpeak": peak_vs_off, "summary": summary}


def list_periods(clips: pd.DataFrame, junction: str) -> list[dict]:
    """Periods a simulation can use for this junction (only those the data supports)."""
    levels = minute_levels(with_pcu(clips))
    lv = levels[levels["junction"] == junction]
    if lv.empty:
        raise KeyError(junction)
    out = [{"id": "all", "label": "All sampled clips", "clips": int(lv["clips"].sum())}]
    for level, name in (("heavy", "peak"), ("light", "off_peak")):
        sel = lv[lv["level"] == level]
        if len(sel):
            out.append({"id": name, "label": f"{'Peak (heavy minutes)' if name == 'peak' else 'Off-peak (light minutes)'}: {', '.join(sel['time'])}", "clips": int(sel["clips"].sum())})
    out += [{"id": f"min:{r.time}", "label": f"Clock minute {r.time} ({r.level})", "clips": int(r.clips)} for r in lv.itertuples() if r.level != "insufficient"]
    return out


def demand_profile(clips: pd.DataFrame, junction: str, period: str) -> dict:
    """Observed demand of one junction in one period: vehicles/hour per direction and class, plus the mean PCU per vehicle."""
    clips = with_pcu(clips)
    jc = clips[clips["Junction"] == junction]
    if jc.empty:
        raise KeyError(junction)
    levels = minute_levels(clips)
    lv = levels[levels["junction"] == junction]
    if period == "all":
        selected = jc
    elif period in ("peak", "off_peak"):
        minutes = lv.loc[lv["level"] == ("heavy" if period == "peak" else "light"), "minute"]
        if minutes.empty:
            raise ValueError(f"{junction} has no {period.replace('_', '-')} minutes in this dataset (see the Peak-Hour page for the method).")
        selected = jc[jc["minute"].isin(minutes)]
    elif re.fullmatch(r"min:\d\d:\d\d", period):
        minute = int(period[4:6]) * 60 + int(period[7:9])
        ok = lv[(lv["minute"] == minute) & (lv["level"] != "insufficient")]
        if ok.empty:
            raise ValueError(f"Clock minute {period[4:]} has fewer than {MIN_CLIPS} clips for {junction}, so it is not used.")
        selected = jc[jc["minute"] == minute]
    else:
        raise ValueError(f"Unknown period '{period}'.")
    rates, pcu_per_veh = {}, {}
    for d in DIRECTIONS:
        dc = selected[selected["Direction"] == d]
        rates[d] = {c: round(_rate(dc, c), 1) for c in CLASSES}
        vehicles = dc["vehicles"].sum()
        pcu_per_veh[d] = round(float(dc["pcu"].sum() / vehicles), 3) if vehicles else round(float(sum(PCU[c] * jc[c].sum() for c in CLASSES) / max(jc["vehicles"].sum(), 1)), 3)
    return {"junction": junction, "period": period, "clip_names": sorted(selected["SourceFile"].unique()), "clips": int(selected["SourceFile"].nunique()), "sampled_s": round(selected["duration_s"].sum() / 4, 1),
            "rates_vph": rates, "vph_by_direction": {d: round(sum(r.values()), 1) for d, r in rates.items()}, "pcu_per_vehicle": pcu_per_veh,
            "pcu_vph_by_direction": {d: round(sum(rates[d].values()) * pcu_per_veh[d], 1) for d in DIRECTIONS}}
