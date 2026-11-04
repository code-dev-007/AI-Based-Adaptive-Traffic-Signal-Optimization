"""Genetic Algorithm that splits one signal cycle between four phases (one phase per modelled approach).

A chromosome is 4 integer green times (seconds). Every chromosome obeys (enforced by `repair`):
  * each green is between min_green and max_green
  * the greens add up to the green budget = cycle length - 4 x lost time per phase
Objective (lower is better), documented so it can be explained in a viva:
    J = sum(q_i * d_i) / sum(q_i)  +  W * sum(max(0, X_i - X_TARGET))  +  penalty for any rule violation
  q_i = demand of phase i (PCU/h)                  d_i = control delay per PCU = d1 + d2  (HCM-2000 pre-timed signal delay)
  d1 = 0.5 C (1 - g/C)^2 / (1 - min(1, X) g/C)      uniform delay          (C = cycle, g = green)
  d2 = 900 T [(X-1) + sqrt((X-1)^2 + 8 k X / (c T))] incremental / overflow delay (T = 0.25 h, k = 0.5)
  X_i = q_i / c_i,  c_i = saturation flow x g/C     degree of saturation (> 1 means the phase is over capacity)
The second term adds a congestion penalty for phases pushed beyond X_TARGET. All values are ESTIMATES from a formula: the
dataset has no signal timings, saturation flows or queue lengths, so SATURATION_FLOW is a configurable assumption.
"""
import math
import random

N_APPROACHES = 4
CYCLE_LENGTH, MIN_GREEN, MAX_GREEN, LOST_TIME = 120, 10, 60, 4      # seconds (defaults)
SATURATION_FLOW = 3600.0   # PCU per hour of green per phase: ASSUMPTION = 2 lanes x 1800 PCU/h/lane
TARGET_X, CONGESTION_WEIGHT = 0.95, 30.0
PERIOD_H, K_PRETIMED = 0.25, 0.5
CONSTRAINT_PENALTY = 1000.0


def green_budget(cycle_length=CYCLE_LENGTH, lost_time=LOST_TIME) -> int:
    return int(cycle_length) - N_APPROACHES * int(lost_time)


def validate_config(cycle_length=CYCLE_LENGTH, min_green=MIN_GREEN, max_green=MAX_GREEN, lost_time=LOST_TIME) -> int:
    """Check the timing settings can be satisfied. Returns the green budget or raises ValueError."""
    if min_green < 1 or lost_time < 0:
        raise ValueError("min_green must be at least 1 second and lost_time cannot be negative.")
    if min_green > max_green:
        raise ValueError(f"min_green ({min_green}) cannot be larger than max_green ({max_green}).")
    budget = green_budget(cycle_length, lost_time)
    if budget < N_APPROACHES * min_green:
        raise ValueError(f"Cycle of {cycle_length}s is too short: {N_APPROACHES} phases need at least "
                         f"{N_APPROACHES * (min_green + lost_time)}s ({min_green}s green + {lost_time}s lost each).")
    if budget > N_APPROACHES * max_green:
        raise ValueError(f"Cycle of {cycle_length}s is too long for max_green={max_green}s: greens could add up to "
                         f"{N_APPROACHES * max_green}s but {budget}s must be allocated.")
    return budget


def constraint_violation(greens, budget, lo, hi) -> float:
    """Total seconds by which `greens` break the rules (0 = valid)."""
    if len(greens) != N_APPROACHES:
        return float("inf")
    return float(sum(max(0, lo - g) + max(0, g - hi) for g in greens) + abs(sum(greens) - budget))


def equal_split(budget: int) -> list[int]:
    """The Fixed-Time plan: the green budget shared equally."""
    base, extra = divmod(budget, N_APPROACHES)
    return [base + (1 if i < extra else 0) for i in range(N_APPROACHES)]


def repair(greens, budget, lo, hi) -> list[int]:
    """Clip to [lo, hi], then add/remove single seconds until the greens sum to the budget."""
    greens = [min(hi, max(lo, int(round(g)))) for g in greens]
    while sum(greens) != budget:
        if sum(greens) > budget:
            i = max((k for k in range(len(greens)) if greens[k] > lo), key=lambda k: greens[k])
            greens[i] -= 1
        else:
            i = min((k for k in range(len(greens)) if greens[k] < hi), key=lambda k: greens[k])
            greens[i] += 1
    return greens


def phase_delay(green, demand, cycle, sat):
    """(estimated delay in s/PCU, degree of saturation X) of one phase."""
    lam = max(green, 1e-6) / cycle
    capacity = sat * lam
    x = demand / capacity
    d1 = 0.5 * cycle * (1 - lam) ** 2 / (1 - min(1.0, x) * lam)
    d2 = 900 * PERIOD_H * ((x - 1) + math.sqrt((x - 1) ** 2 + 8 * K_PRETIMED * x / (capacity * PERIOD_H)))
    return d1 + d2, x


def fitness(greens, demand, cycle, sat, budget, lo, hi) -> float:
    total = sum(demand) or 1.0
    delay, congestion = 0.0, 0.0
    for g, q in zip(greens, demand):
        d, x = phase_delay(g, q, cycle, sat)
        delay += q * d
        congestion += max(0.0, x - TARGET_X)
    return delay / total + CONGESTION_WEIGHT * congestion + CONSTRAINT_PENALTY * constraint_violation(greens, budget, lo, hi)


def _tournament(population, scores, rng, k=3):
    return population[min(rng.sample(range(len(population)), k), key=lambda i: scores[i])]


def _mutate(greens, rng, rate, budget, lo, hi, step=8):
    """With probability `rate`, move up to `step` seconds from one phase to another."""
    greens = list(greens)
    if rng.random() < rate:
        src, dst = rng.sample(range(N_APPROACHES), 2)
        greens[src] -= rng.randint(1, step)
        greens[dst] += rng.randint(1, step)
    return repair(greens, budget, lo, hi)


def optimize(demand, cycle_length=CYCLE_LENGTH, min_green=MIN_GREEN, max_green=MAX_GREEN, lost_time=LOST_TIME,
             saturation_flow=SATURATION_FLOW, population_size=40, generations=60, mutation_rate=0.3, elite_count=2,
             seed=42, baseline=None) -> dict:
    """Find green times for 4 phases. `demand` = 4 values in PCU/h. `baseline` = the Fixed-Time plan to compare with
    (default: equal split). The baseline is in the starting population, so the result is never worse than it."""
    if len(demand) != N_APPROACHES or min(demand) < 0:
        raise ValueError(f"Provide {N_APPROACHES} non-negative demand values.")
    if saturation_flow <= 0:
        raise ValueError("saturation_flow must be positive.")
    budget = validate_config(cycle_length, min_green, max_green, lost_time)
    lo, hi, rng = int(min_green), int(max_green), random.Random(seed)
    fixed = repair(baseline, budget, lo, hi) if baseline else equal_split(budget)

    def score(ind):
        return fitness(ind, demand, cycle_length, saturation_flow, budget, lo, hi)

    population = [repair([rng.randint(lo, hi) for _ in range(N_APPROACHES)], budget, lo, hi) for _ in range(population_size - 1)] + [fixed]
    history = []
    for _ in range(generations):
        scores = [score(ind) for ind in population]
        ranked = sorted(range(len(population)), key=lambda i: scores[i])
        history.append(scores[ranked[0]])
        next_gen = [population[i] for i in ranked[:elite_count]]  # elitism
        while len(next_gen) < population_size:
            a, b = _tournament(population, scores, rng), _tournament(population, scores, rng)
            child = repair([x if rng.random() < 0.5 else y for x, y in zip(a, b)], budget, lo, hi)  # uniform crossover
            next_gen.append(_mutate(child, rng, mutation_rate, budget, lo, hi))
        population = next_gen
    best = min(population, key=score)
    fixed_fit, best_fit = score(fixed), score(best)
    details = lambda plan: [{"green_s": g, "demand_pcu_h": round(q, 1), "x": round(phase_delay(g, q, cycle_length, saturation_flow)[1], 3),  # noqa: E731
                             "delay_s": round(phase_delay(g, q, cycle_length, saturation_flow)[0], 1),
                             "queue_pcu": round(q / 3600 * (cycle_length - g), 1)} for g, q in zip(plan, demand)]
    return {"greens": best, "fixed_greens": fixed, "cycle_length": sum(best) + N_APPROACHES * lost_time, "fitness": best_fit, "fixed_fitness": fixed_fit,
            "improvement_pct": 100 * (fixed_fit - best_fit) / fixed_fit if fixed_fit > 0 else 0.0,
            "optimized": details(best), "fixed": details(fixed), "history": history, "demand_pcu_h": [float(q) for q in demand],
            "constraints": {"min_green": lo, "max_green": hi, "cycle_length": int(cycle_length), "lost_time_per_phase": int(lost_time),
                            "green_budget": budget, "violation_s": constraint_violation(best, budget, lo, hi),
                            "saturation_flow_pcu_h": saturation_flow}}


def explain(result: dict, names: list[str]) -> list[str]:
    """Plain-language reasons for the chosen timings, built from the result itself."""
    total = sum(result["demand_pcu_h"]) or 1.0
    lines = []
    for name, new, old, q in zip(names, result["optimized"], result["fixed"], result["demand_pcu_h"]):
        change = new["green_s"] - old["green_s"]
        verb = "more" if change > 0 else "less" if change < 0 else "the same"
        lines.append(f"{name}: {abs(change)} s {verb} green than Fixed-Time ({old['green_s']} s -> {new['green_s']} s). It carries "
                     f"{100 * q / total:.0f}% of the demand (equal split gives 25%); degree of saturation {old['x']:.2f} -> {new['x']:.2f}.")
    old_delay = sum(o["delay_s"] * q for o, q in zip(result["fixed"], result["demand_pcu_h"])) / total
    new_delay = sum(o["delay_s"] * q for o, q in zip(result["optimized"], result["demand_pcu_h"])) / total
    lines.append(f"Estimated average delay (formula, not measured): {old_delay:.1f} s -> {new_delay:.1f} s per PCU.")
    if max(o["x"] for o in result["optimized"]) > 1:
        lines.append("At least one phase is still over capacity (X > 1): no split of this cycle can serve this demand; expect growing queues.")
    return lines
