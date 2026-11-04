import { motion } from "framer-motion";
import { Flag, Gauge, Pause, Play, RotateCcw, Timer, Users } from "lucide-react";
import { useState } from "react";
import { api, errorMessage } from "../api/client.js";
import { LineBox } from "../components/charts.jsx";
import ComparisonView from "../components/ComparisonView.jsx";
import ScenarioPicker, { initialScenario } from "../components/ScenarioPicker.jsx";
import { Async, Button, Card, Empty, ErrorBox, Note, NumberInput, Select, Stat, Tag, useToast } from "../components/ui.jsx";
import { useApi } from "../hooks/useApi.js";
import { useSettings } from "../hooks/useSettings.js";
import { useSimulationSocket } from "../hooks/useSimulationSocket.js";
import { DIRECTIONS, DIR_COLORS, mmss, num } from "../utils.js";

const LAMP = { GREEN: "#22c55e", YELLOW: "#facc15", RED: "#ef4444" };
// Each arm is drawn once pointing up and rotated; queue squares are real queued vehicles from the backend (max 16 drawn).
const ROTATE = { UP: 0, RIGHT: 90, DOWN: 180, LEFT: 270 };

function Intersection({ state }) {
  return (
    <svg viewBox="0 0 520 420" className="mx-auto w-full max-w-xl" role="img" aria-label={`Intersection: queues ${DIRECTIONS.map((d, i) => `${d} ${state.metrics.queues[i]}`).join(", ")} vehicles`}>
      <rect width="520" height="420" rx="14" fill="#0d1527" />
      <rect x="220" y="0" width="80" height="420" fill="#1b2744" /><rect x="0" y="170" width="520" height="80" fill="#1b2744" />
      {DIRECTIONS.map((d, i) => {
        const queue = state.metrics.queues[i], shown = Math.min(queue, 16);
        return (
          <g key={d} transform={`rotate(${ROTATE[d]} 260 210)`}>
            <rect x="220" y="163" width="80" height="6" fill={LAMP[state.signals[i]]} />
            {Array.from({ length: shown }, (_, k) => <rect key={k} x={228 + (k % 2) * 40} y={146 - Math.floor(k / 2) * 18} width="22" height="13" rx="3" fill={DIR_COLORS[d]} />)}
            {queue > 16 && <text x="260" y="14" textAnchor="middle" fill="#e6edf7" fontSize="13" transform={ROTATE[d] ? `rotate(${-ROTATE[d]} 260 8)` : undefined}>+{queue - 16} more</text>}
          </g>);
      })}
      {[["UP", 310, 24, "start"], ["DOWN", 210, 404, "end"], ["RIGHT", 508, 164, "end"], ["LEFT", 12, 274, "start"]].map(([d, x, y, anchor]) => {
        const i = DIRECTIONS.indexOf(d);
        return <text key={d} x={x} y={y} textAnchor={anchor} fill="#e6edf7" fontSize="13" fontWeight="600">{d}: {state.signals[i]}, queue {state.metrics.queues[i]}</text>;
      })}
    </svg>
  );
}

export default function Simulation({ goTo }) {
  const dataset = useApi(api.dataset);
  return <Async state={dataset}>{(d) => <View dataset={d} goTo={goTo} />}</Async>;
}

function View({ dataset }) {
  const { settings } = useSettings();
  const toast = useToast();
  const [scenario, setScenario] = useState(initialScenario(dataset));
  const [cfg, setCfg] = useState({ controller: "adaptive", duration: 900, seed: 42 });
  const [speed, setSpeed] = useState(30);
  const [error, setError] = useState(null);
  const [compare, setCompare] = useState({ busy: false, data: null });
  const { state, setState, connected } = useSimulationSocket(speed);
  const act = (call, okText) => async () => {
    setError(null);
    try { setState(await call()); okText && toast(okText); } catch (e) { setError(errorMessage(e)); toast(errorMessage(e), "error"); }
  };
  const start = act(() => api.simStart({ ...settings, ...scenario, ...cfg }), "Simulation started.");
  const runCompare = async () => {
    setCompare({ busy: true, data: null });
    try { setCompare({ busy: false, data: await api.experiment({ ...settings, ...scenario, duration: cfg.duration, base_seed: cfg.seed, n_seeds: 3 }) }); toast("Comparison finished and saved to Experiment History."); }
    catch (e) { setCompare({ busy: false, data: null }); toast(errorMessage(e), "error"); }
  };
  const m = state?.metrics;
  const history = state?.history.map((p) => ({ ...p })) ?? [];
  return (
    <div className="space-y-5">
      <Card title="Scenario and controls" subtitle="The backend runs the simulation second by second and streams its state here">
        <ScenarioPicker dataset={dataset} value={scenario} onChange={setScenario}>
          <Select label="Controller" value={cfg.controller} onChange={(e) => setCfg({ ...cfg, controller: e.target.value })} options={[{ value: "adaptive", label: "Adaptive (ML + Genetic Algorithm)" }, { value: "fixed", label: "Fixed-Time" }]} />
          <NumberInput label="Duration (s)" min={60} max={7200} step={60} value={cfg.duration} onChange={(v) => setCfg({ ...cfg, duration: v })} />
          <NumberInput label="Random seed" min={0} max={999999} value={cfg.seed} onChange={(v) => setCfg({ ...cfg, seed: v })} hint="Same seed, same arrivals" />
          <label className="block text-sm font-medium">Speed: {speed} simulated s per real s<input type="range" min="5" max="300" step="5" value={speed} onChange={(e) => setSpeed(Number(e.target.value))} className="mt-3 w-full accent-cyan-400" /></label>
        </ScenarioPicker>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button variant="primary" icon={Play} onClick={start} disabled={cfg.duration === ""}>Start</Button>
          <Button icon={state?.running ? Pause : Play} disabled={!state || state.finished} onClick={act(state?.running ? api.simPause : api.simResume)}>{state?.running ? "Pause" : "Resume"}</Button>
          <Button icon={RotateCcw} disabled={!state} onClick={act(api.simReset)}>Reset</Button>
          <span className={`text-xs ${connected ? "text-good" : "text-bad"}`}>{connected ? "Live stream connected" : "Live stream disconnected, reconnecting..."}</span>
        </div>
        {error && <div className="mt-3"><ErrorBox message={error} /></div>}
      </Card>
      <Note>Each direction of the junction is modelled as one signal group with its own phase and queue (an assumption: the CSV does not describe the real layout). Vehicles arrive randomly at the observed rates; buses and trucks need more green time than bikes. Everything on this page is simulated.</Note>
      {!state ? <Empty icon={Play} title="No simulation running" text="Press Start to simulate the selected scenario." /> : (
        <>
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
            <Card title="Intersection" tag="simulated" subtitle={`${state.meta.scenario}, ${state.controller === "adaptive" ? "Adaptive" : "Fixed-Time"} controller`}>
              <Intersection state={state} />
              <div className="mt-3 flex items-center gap-3 text-sm"><span className="font-mono text-lg">{mmss(m.time_s)}</span><div className="h-2 flex-1 overflow-hidden rounded-full bg-raised" role="progressbar" aria-valuenow={m.time_s} aria-valuemax={state.duration_s}>
                <motion.div className="h-full bg-cyan" animate={{ width: `${(100 * m.time_s) / state.duration_s}%` }} /></div><span className="text-muted">{mmss(state.duration_s)}</span></div>
              <p className="mt-1 text-xs text-muted">Green plan (s): {DIRECTIONS.map((d, i) => `${d} ${state.greens[i]}`).join(", ")}{state.finished ? ". Finished and saved to Experiment History." : state.running ? "" : ". Paused."}</p>
            </Card>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <Stat label="Arrived" icon={Users} value={m.arrived} unit="veh" sub="simulated" />
                <Stat label="Served" icon={Flag} tone="good" value={m.served} unit="veh" sub={`${num(m.throughput_vph, 0)} veh/h`} />
                <Stat label="Avg wait" icon={Timer} tone="warn" value={num(m.avg_wait_s, 0)} unit="s" sub={`max ${num(m.max_wait_s, 0)} s`} />
                <Stat label="Max queue" icon={Gauge} tone="blue" value={m.max_queue} unit="veh" sub={`avg ${num(m.avg_queue)} veh`} />
              </div>
              <Card title="Queue length over time" tag="simulated"><LineBox height={220} data={history} xKey="t" xTick={mmss} xLabel="Simulated time" yLabel="Vehicles queued" series={DIRECTIONS.map((d) => ({ key: d, color: DIR_COLORS[d] }))} /></Card>
            </div>
          </div>
          {state.plans.length > 0 && <Note>Latest Adaptive re-plans (green seconds UP/DOWN/RIGHT/LEFT): {state.plans.map((p) => `${mmss(p.t)} -> ${p.greens.join("/")}`).join(", ")}</Note>}
        </>)}
      <Card title="Fixed-Time vs Adaptive on this scenario" tag="simulated" subtitle="Runs both controllers to the end of the duration on identical arrivals (3 seeds) and saves the result"
            actions={<Button variant="primary" busy={compare.busy} onClick={runCompare}>Compare controllers</Button>}>
        {compare.data ? <ComparisonView r={compare.data} /> : <p className="text-sm text-muted">Use this to see the controllers side by side. Adaptive can lose when demand is light or far above capacity; the numbers are shown as they come out.</p>}
      </Card>
    </div>
  );
}
