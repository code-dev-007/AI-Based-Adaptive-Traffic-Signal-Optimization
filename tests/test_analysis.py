import pandas as pd
import pytest

from backend import analysis as an
from backend.preprocessing import CLASSES, DIRECTIONS


def fake_clips(per_minute):
    """per_minute: {(minute, n_clips): vehicles_per_clip_direction} for one junction 'J'."""
    rows = []
    for (minute, n), veh in per_minute.items():
        for k in range(n):
            for d in DIRECTIONS:
                rows.append({"Date": "2023-01-11", "Camera": "x1", "Junction": "J", "SourceFile": f"c{minute}_{k}", "Direction": d, "start_s": minute * 60.0, "duration_s": 8.0,
                             "car": veh, **{c: 0 for c in CLASSES[1:]}, "vehicles": veh})
    return pd.DataFrame(rows)


def test_peak_light_and_insufficient_levels_follow_the_documented_thresholds():
    clips = an.with_pcu(fake_clips({(540, 4): 1, (541, 4): 10, (542, 4): 4, (543, 1): 1}))
    levels = an.minute_levels(clips).set_index("time")["level"].to_dict()
    assert levels == {"09:00": "light", "09:01": "heavy", "09:02": "moderate", "09:03": "insufficient"}


def test_peak_is_discovered_from_data_not_assumed(pipeline):
    result = an.peak_analysis(pipeline["clips"])
    assert result["overall_peak"]["time"] == "11:26" and result["overall_peak"]["of"] == 3
    hours = {h["hour"]: h["rate_vph"] for h in result["by_hour"]}
    assert hours[10] is None  # no clips at 10:xx, so no value is invented
    assert not any("weekday" in k for k in result)


def test_demand_profile_uses_observed_rates_and_rejects_unsupported_periods(pipeline):
    p = an.demand_profile(pipeline["clips"], "JehangirChowk", "all")
    assert p["clips"] == 43 and set(p["vph_by_direction"]) == set(DIRECTIONS) and all(v >= 0 for v in p["pcu_vph_by_direction"].values())
    with pytest.raises(ValueError):
        an.demand_profile(pipeline["clips"], "JehangirChowk", "min:11:23")   # only 0 clips: not supported
    with pytest.raises(ValueError):
        an.demand_profile(pipeline["clips"], "JehangirChowk", "min:11:2x")
    with pytest.raises(KeyError):
        an.demand_profile(pipeline["clips"], "Nowhere", "all")


def test_date_wise_results_never_mix_dates_and_invent_no_rows(pipeline):
    r = an.peak_analysis(pipeline["clips"])
    assert len(r["dates"]) == 8 and {b["date"] for b in r["by_date"]} == set(r["dates"])
    assert len(r["by_date"]) == 24  # 3 junctions x 8 dates, each with real clips
    assert sum(b["vehicles"] for b in r["by_date"]) == 760 == r["total_vehicles"]
    assert all(b["clips"] > 0 and b["sampled_s"] > 0 for b in r["by_date"])
    assert sum(w["vehicles"] for w in r["date_windows"]) == 760  # windows split each date, nothing is added or lost
    assert r["busiest_overall"]["date"] in r["dates"] and r["busiest_overall"]["sampled_s"] >= an.MIN_WINDOW_S
    assert [x["title"] for x in r["limitations"]][:3] == ["Limited Observation Coverage", "Short Observation Duration", "Observed Peak Window"]
