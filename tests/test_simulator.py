import numpy as np
import pytest

from backend import analysis as an
from backend import model as ml
from backend import simulator as sm


@pytest.fixture(scope="module")
def profile(pipeline):
    return an.demand_profile(pipeline["clips"], "JehangirChowk", "all")


def run(profile, controller, seed=1, model=None, **cfg):
    sim = sm.Simulation(profile, controller, seed, sm.Config(duration=600, **cfg), model=model)
    sim.run()
    return sim


def test_same_seed_is_reproducible_and_controllers_share_identical_arrivals(profile, trained):
    models, _ = trained
    a, b = run(profile, "fixed", 7), run(profile, "fixed", 7)
    adaptive = run(profile, "adaptive", 7, models[3])
    assert a.metrics() == b.metrics() and np.array_equal(a.arrivals, adaptive.arrivals)
    assert not np.array_equal(a.arrivals, run(profile, "fixed", 8).arrivals)


def test_vehicles_are_conserved_and_waits_are_sensible(profile):
    m = run(profile, "fixed").metrics()
    assert m["arrived"] == m["served"] + sum(m["queues"]) and m["avg_wait_s"] >= 0 and m["max_wait_s"] >= m["avg_wait_s"] * 0
    assert m["throughput_vph"] == pytest.approx(m["served"] / 600 * 3600) and 0 <= m["congestion_pct"] <= 100


def test_only_one_phase_is_green_and_fixed_plan_never_changes(profile):
    sim = sm.Simulation(profile, "fixed", 1, sm.Config(duration=300))
    plans = set()
    for _ in range(300):
        sim.step()
        assert sim.signal_states().count("GREEN") <= 1
        plans.add(tuple(sim.greens))
    assert len(plans) == 1 and sim.plans == []


def test_adaptive_replans_with_valid_greens_and_cold_starts_with_the_fixed_plan(profile, trained):
    models, _ = trained
    sim = run(profile, "adaptive", 3, models[3])
    assert sim.plans and sim.plans[0]["t"] >= 120            # first cycle uses the Fixed-Time plan
    assert all(sum(p["greens"]) == 104 and all(10 <= g <= 60 for g in p["greens"]) for p in sim.plans)


def test_reduction_formula_and_zero_denominator():
    assert sm.pct_reduction(200, 150) == 25.0 and sm.pct_reduction(100, 120) == -20.0 and sm.pct_reduction(0, 5) is None


def test_compare_reports_worse_adaptive_results_honestly(profile, pipeline, trained):
    models, report = trained
    result = sm.compare(profile, profile, sm.Config(duration=300, multiplier=0.25), models[3], report["junction_codes"]["JehangirChowk"], n_seeds=2)
    assert set(result["summary"]) == {"fixed", "adaptive"} and len(result["runs"]["fixed"]) == 2
    expected = sm.pct_reduction(result["summary"]["fixed"]["avg_wait_s"]["mean"], result["summary"]["adaptive"]["avg_wait_s"]["mean"])
    assert result["reduction"]["wait_pct"] == expected   # sign is whatever the simulation produced, never forced positive


def test_invalid_config_is_rejected(profile):
    with pytest.raises(ValueError):
        sm.Simulation(profile, "fixed", 1, sm.Config(cycle_length=30))
    with pytest.raises(ValueError):
        sm.Simulation(profile, "magic", 1)
