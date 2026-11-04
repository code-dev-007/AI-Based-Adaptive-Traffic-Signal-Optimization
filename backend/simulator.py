"""One-second simulator of a four-phase signal: Fixed-Time vs Adaptive (ML demand prediction + Genetic Algorithm).

EVERYTHING produced here is SIMULATED. Observed data only sets the arrival rates:
  * each direction of the chosen junction is one signal group with its own queue and its own phase (an ASSUMPTION: the CSV does
    not say how UP/DOWN/LEFT/RIGHT map to a physical road layout);
  * arrivals are Poisson per second, separately per vehicle class, with rates = observed vehicles/hour x demand multiplier;
  * vehicles are not all equal: a queue holds individual vehicles and a bus/truck needs more discharge capacity (PCU) than a bike;
  * no vehicle trajectories or speeds exist in the data, so none are simulated: a vehicle waits in a queue until it is discharged.
For one seed both controllers get exactly the same arrivals, so the comparison is fair and reproducible.
"""
from collections import deque
from dataclasses import asdict, dataclass

import numpy as np

from backend import genetic_algorithm as ga
from backend import model as ml
from backend import preprocessing as pp

YELLOW = 3  # seconds of yellow at the start of every lost-time period (the rest is all-red)
HISTORY_EVERY = 10  # seconds between chart points
HISTORY_WINDOW = 60  # seconds of recent arrivals the Adaptive controller shows the model


@dataclass
class Config:
    duration: int = 1800                  # simulated seconds
    multiplier: float = 1.0               # demand multiplier (what-if scaling of the observed rates)
    cycle_length: int = ga.CYCLE_LENGTH
    min_green: int = ga.MIN_GREEN
    max_green: int = ga.MAX_GREEN
    lost_time: int = ga.LOST_TIME
    saturation_flow: float = ga.SATURATION_FLOW  # PCU/h of green per phase (ASSUMPTION)
    reopt_s: int = ga.CYCLE_LENGTH        # Adaptive re-plans at the first cycle start after this many seconds
    congestion_queue: int = 15            # a phase counts as congested while its queue holds at least this many vehicles
    fixed_plan: str = "equal"             # "equal" split, or "historical" = GA plan for the junction's overall observed demand


def pct_reduction(fixed, adaptive):
    """(fixed - adaptive) / fixed x 100, or None when fixed is 0 (nothing to reduce)."""
    return None if not fixed else 100 * (fixed - adaptive) / fixed


class Simulation:
    def __init__(self, profile: dict, controller="fixed", seed=42, config: Config | None = None, fixed_greens=None, model=None, junction_code=0):
        if controller not in ("fixed", "adaptive"):
            raise ValueError("controller must be 'fixed' or 'adaptive'")
        self.cfg, self.controller, self.seed, self.profile = config or Config(), controller, seed, profile
        self.model, self.junction_code = model, junction_code
        budget = ga.validate_config(self.cfg.cycle_length, self.cfg.min_green, self.cfg.max_green, self.cfg.lost_time)
        self.fixed_greens = fixed_greens or ga.equal_split(budget)
        self.pcu_per_vehicle = [profile["pcu_per_vehicle"][d] for d in pp.DIRECTIONS]
        rates = np.array([[profile["rates_vph"][d][c] for c in pp.CLASSES] for d in pp.DIRECTIONS]) / 3600 * self.cfg.multiplier
        self.arrivals = np.random.default_rng(seed).poisson(rates, size=(self.cfg.duration, 4, 4))  # (second, direction, class)
        self.reset()

    def reset(self):
        self.t, self.phase, self.phase_time = 0, 0, 0
        self.greens, self.plans = list(self.fixed_greens), []
        self.queues = [deque() for _ in range(4)]       # (arrival second, PCU size) of each waiting vehicle
        self.credit = [0.0] * 4                          # unused discharge capacity (PCU)
        self.arrived, self.served = [0] * 4, [0] * 4
        self.wait_served, self.max_wait = [0.0] * 4, 0
        self.queue_sum, self.max_queue, self.congested_s, self.served_pcu = 0, 0, 0, 0.0
        self.last_plan_t, self.history, self.running, self.saved = 0, [], False, False

    # ---- controller -------------------------------------------------------
    def _new_plan(self):
        """Greens for the next cycle. Fixed: never changes. Adaptive: model-predicted demand -> Genetic Algorithm."""
        if self.controller == "fixed" or self.t < 10 or self.t - self.last_plan_t < self.cfg.reopt_s:
            return self.greens  # Fixed-Time, the cold start (first cycle uses the Fixed-Time plan) or between re-plans
        window = self.arrivals[max(0, self.t - HISTORY_WINDOW): self.t] / max(self.cfg.multiplier, 1e-9)  # back to the observed scale
        rate = ml.demand_rate(self.model, window, self.junction_code)                                       # predicted veh/s per direction
        demand = [float(r * self.cfg.multiplier * 3600 * p) for r, p in zip(rate, self.pcu_per_vehicle)]  # PCU/h
        c = self.cfg
        result = ga.optimize(demand, c.cycle_length, c.min_green, c.max_green, c.lost_time, c.saturation_flow, 30, 30,
                             seed=self.seed + self.t, baseline=self.fixed_greens)
        self.plans.append({"t": self.t, "greens": result["greens"], "demand_pcu_h": [round(v, 1) for v in demand]})
        self.last_plan_t = self.t
        return result["greens"]

    def signal_states(self):
        states = ["RED"] * 4
        yellow = min(YELLOW, self.cfg.lost_time)
        if self.phase_time < self.greens[self.phase]:
            states[self.phase] = "GREEN"
        elif self.phase_time < self.greens[self.phase] + yellow:
            states[self.phase] = "YELLOW"
        return states

    # ---- one simulated second ---------------------------------------------
    def step(self):
        if self.t >= self.cfg.duration:
            self.running = False
            return
        if self.phase == 0 and self.phase_time == 0:
            self.greens = self._new_plan()                # the plan is fixed for the whole cycle
        for d in range(4):
            for k, size in enumerate(pp.PCU.values()):
                n = int(self.arrivals[self.t, d, k])
                self.queues[d].extend([(self.t, size)] * n)
                self.arrived[d] += n
        d = self.phase
        if self.phase_time < self.greens[d]:             # green: discharge at the saturation flow
            self.credit[d] += self.cfg.saturation_flow / 3600
            while self.queues[d] and self.credit[d] >= self.queues[d][0][1]:
                arrival, size = self.queues[d].popleft()
                self.credit[d] -= size
                self.served[d] += 1
                self.served_pcu += size
                self.wait_served[d] += self.t - arrival
                self.max_wait = max(self.max_wait, self.t - arrival)
            if not self.queues[d]:
                self.credit[d] = 0.0
        lengths = [len(q) for q in self.queues]
        self.queue_sum += sum(lengths)
        self.max_queue = max(self.max_queue, sum(lengths))
        self.congested_s += max(lengths) >= self.cfg.congestion_queue
        self.t += 1
        self.phase_time += 1
        if self.phase_time >= self.greens[d] + self.cfg.lost_time:
            self.phase, self.phase_time = (self.phase + 1) % 4, 0
        if self.t % HISTORY_EVERY == 0:
            self.history.append({"t": self.t, **{name: n for name, n in zip(pp.DIRECTIONS, lengths)}})

    def advance(self, seconds):
        for _ in range(int(seconds)):
            self.step()

    def run(self):
        self.advance(self.cfg.duration)
        return self.metrics()

    # ---- results (all simulated) ------------------------------------------
    def metrics(self) -> dict:
        waiting = [sum(self.t - a for a, _ in q) for q in self.queues]  # vehicles still queued count their wait so far
        oldest = max((self.t - q[0][0] for q in self.queues if q), default=0)
        arrived, t = sum(self.arrived), max(self.t, 1)
        return {"time_s": self.t, "arrived": arrived, "served": sum(self.served), "served_pcu": round(self.served_pcu, 1),
                "avg_wait_s": (sum(self.wait_served) + sum(waiting)) / arrived if arrived else 0.0, "max_wait_s": max(self.max_wait, oldest),
                "avg_queue": self.queue_sum / t, "max_queue": self.max_queue, "queues": [len(q) for q in self.queues],
                "throughput_vph": sum(self.served) / t * 3600, "congestion_pct": 100 * self.congested_s / t,
                "by_direction": [{"direction": n, "arrived": a, "served": s, "avg_wait_s": (w + x) / a if a else 0.0}
                                 for n, a, s, w, x in zip(pp.DIRECTIONS, self.arrived, self.served, self.wait_served, waiting)]}

    def snapshot(self) -> dict:
        return {"controller": self.controller, "running": self.running, "finished": self.t >= self.cfg.duration, "duration_s": self.cfg.duration,
                "signals": self.signal_states(), "greens": list(self.greens), "phase": self.phase, "phase_time": self.phase_time,
                "metrics": self.metrics(), "history": self.history, "plans": self.plans[-5:], "config": asdict(self.cfg)}


def fixed_plan_greens(cfg: Config, overall_profile: dict) -> list[int]:
    """Fixed-Time plan: an equal split, or a GA plan tuned once for the junction's overall observed demand (not scaled)."""
    if cfg.fixed_plan == "historical":
        demand = [overall_profile["pcu_vph_by_direction"][d] for d in pp.DIRECTIONS]
        return ga.optimize(demand, cfg.cycle_length, cfg.min_green, cfg.max_green, cfg.lost_time, cfg.saturation_flow, seed=0)["greens"]
    return ga.equal_split(ga.validate_config(cfg.cycle_length, cfg.min_green, cfg.max_green, cfg.lost_time))


COMPARED = ("avg_wait_s", "max_wait_s", "avg_queue", "max_queue", "served", "throughput_vph", "congestion_pct")


def compare(profile: dict, overall_profile: dict, cfg: Config, model, junction_code: int, n_seeds=3, base_seed=42) -> dict:
    """Run Fixed-Time and Adaptive on identical arrivals for n_seeds seeds. Returns per-seed results, mean/std and the reductions."""
    fixed = fixed_plan_greens(cfg, overall_profile)
    runs, examples = {"fixed": [], "adaptive": []}, {}
    for k in range(n_seeds):
        for name in runs:
            sim = Simulation(profile, name, base_seed + k, cfg, fixed, model, junction_code)
            result = {"seed": base_seed + k, **sim.run()}
            runs[name].append(result)
            if k == 0:
                examples[name] = sim.snapshot()
    summary = {name: {m: {"mean": float(np.mean([r[m] for r in rs])), "std": float(np.std([r[m] for r in rs]))} for m in COMPARED} for name, rs in runs.items()}
    mean = lambda name, m: summary[name][m]["mean"]  # noqa: E731
    reduction = {"wait_pct": pct_reduction(mean("fixed", "avg_wait_s"), mean("adaptive", "avg_wait_s")),
                 "queue_pct": pct_reduction(mean("fixed", "avg_queue"), mean("adaptive", "avg_queue")),
                 "congestion_pct": pct_reduction(mean("fixed", "congestion_pct"), mean("adaptive", "congestion_pct")),
                 "throughput_change_pct": -pct_reduction(mean("fixed", "throughput_vph"), mean("adaptive", "throughput_vph")) if mean("fixed", "throughput_vph") else None}
    return {"summary": summary, "reduction": reduction, "runs": runs, "examples": examples, "fixed_greens": fixed, "n_seeds": n_seeds}
