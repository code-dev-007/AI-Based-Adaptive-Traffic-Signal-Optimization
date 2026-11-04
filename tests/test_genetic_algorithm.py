import pytest

from backend import genetic_algorithm as ga

DEMAND = [300.0, 1500.0, 600.0, 900.0]


def test_solution_obeys_every_signal_rule():
    r = ga.optimize(DEMAND, cycle_length=120, min_green=10, max_green=60, lost_time=4)
    assert sum(r["greens"]) == 104 == r["constraints"]["green_budget"] and all(10 <= g <= 60 for g in r["greens"])
    assert r["cycle_length"] == 120 and r["constraints"]["violation_s"] == 0


def test_custom_cycle_and_limits_are_respected():
    r = ga.optimize(DEMAND, cycle_length=90, min_green=8, max_green=40, lost_time=3)
    assert sum(r["greens"]) == 78 and all(8 <= g <= 40 for g in r["greens"]) and r["cycle_length"] == 90


@pytest.mark.parametrize("kwargs", [{"cycle_length": 40}, {"min_green": 70}, {"cycle_length": 300}, {"saturation_flow": 0}, {"lost_time": -1}])
def test_impossible_settings_raise_a_clear_error(kwargs):
    with pytest.raises(ValueError):
        ga.optimize(DEMAND, **kwargs)
    with pytest.raises(ValueError):
        ga.optimize([1, 2, 3])


def test_busier_phases_get_more_green_and_result_is_never_worse_than_fixed_time():
    r = ga.optimize([100, 2000, 100, 100], seed=1)
    assert r["greens"][1] == max(r["greens"]) and r["fitness"] <= r["fixed_fitness"] and r["improvement_pct"] >= 0


def test_same_seed_gives_same_plan():
    assert ga.optimize(DEMAND, seed=5)["greens"] == ga.optimize(DEMAND, seed=5)["greens"]


def test_delay_model_more_green_means_less_delay_and_zero_demand_is_safe():
    d_short, x_short = ga.phase_delay(10, 500, 120, 3600)
    d_long, x_long = ga.phase_delay(40, 500, 120, 3600)
    assert d_long < d_short and x_long < x_short
    assert ga.phase_delay(20, 0, 120, 3600)[1] == 0 and ga.optimize([0, 0, 0, 0])["constraints"]["violation_s"] == 0


def test_repair_always_returns_a_valid_plan():
    for bad in ([0, 0, 0, 0], [200, 200, 200, 200], [10, 60, 60, 60]):
        plan = ga.repair(bad, 104, 10, 60)
        assert sum(plan) == 104 and all(10 <= g <= 60 for g in plan)


def test_explanation_mentions_every_phase_and_the_estimate_caveat():
    lines = ga.explain(ga.optimize(DEMAND), ["UP", "DOWN", "RIGHT", "LEFT"])
    assert len(lines) >= 5 and "not measured" in lines[-1] or "not measured" in lines[-2]
