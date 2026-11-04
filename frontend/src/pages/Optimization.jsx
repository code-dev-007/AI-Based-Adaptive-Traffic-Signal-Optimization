import { CheckCircle2, Cpu, XCircle } from "lucide-react";
import { useState } from "react";
import { api, errorMessage } from "../api/client.js";
import { BarBox } from "../components/charts.jsx";
import ScenarioPicker, { initialScenario } from "../components/ScenarioPicker.jsx";
import { Async, Button, Card, Empty, ErrorBox, Note, NumberInput, Select, Table, Tag, useToast } from "../components/ui.jsx";
import { useApi } from "../hooks/useApi.js";
import { useSettings } from "../hooks/useSettings.js";
import { CTRL_COLORS, DIRECTIONS, DIR_COLORS, num } from "../utils.js";

export default function Optimization() {
  const dataset = useApi(api.dataset);
  return <Async state={dataset}>{(d) => <View dataset={d} />}</Async>;
}

/** Horizontal signal-phase bar: one coloured green segment per phase followed by its lost time (yellow + all-red). */
function PhaseBar({ title, greens, lost, cycle }) {
  return (
    <div className="mb-3"><p className="mb-1 text-sm font-medium">{title} <span className="text-muted">(cycle {cycle} s)</span></p>
      <div className="flex h-10 overflow-hidden rounded-lg border border-line" role="img" aria-label={`${title}: ${greens.map((g, i) => `${DIRECTIONS[i]} ${g} s`).join(", ")}`}>
        {greens.map((g, i) => (<div key={i} className="flex" style={{ width: `${((g + lost) / cycle) * 100}%` }}>
          <div className="flex flex-1 items-center justify-center text-xs font-semibold text-page" style={{ background: DIR_COLORS[DIRECTIONS[i]] }}>{DIRECTIONS[i]} {g}s</div>
          <div className="bg-warn/70" style={{ width: `${(lost / (g + lost)) * 100}%` }} title={`${lost} s lost time (yellow + all-red)`} />
        </div>))}
      </div></div>
  );
}

function View({ dataset }) {
  const { settings } = useSettings();
  const toast = useToast();
  const [scenario, setScenario] = useState(initialScenario(dataset));
  const [source, setSource] = useState("predicted");
  const [manual, setManual] = useState([400, 800, 300, 500]);
  const [timing, setTiming] = useState({ cycle_length: settings.cycle_length, min_green: settings.min_green, max_green: settings.max_green, lost_time: settings.lost_time });
  const [state, setState] = useState({ data: null, error: null, busy: false });
  const setT = (k) => (v) => setTiming({ ...timing, [k]: v });
  const valid = Object.values(timing).every((v) => v !== "") && manual.every((v) => v !== "");
  const run = async () => {
    setState({ data: null, error: null, busy: true });
    try {
      const data = await api.optimize({ ...settings, ...timing, ...scenario, source, manual_vph: source === "manual" ? manual : undefined });
      setState({ data, error: null, busy: false });
      toast("Signal timings optimized.");
    } catch (e) { setState({ data: null, error: errorMessage(e), busy: false }); toast(errorMessage(e), "error"); }
  };
  const r = state.data;
  const check = r && [[`Greens + lost time = cycle (${r.greens.reduce((a, b) => a + b, 0)} + ${4 * r.constraints.lost_time_per_phase} = ${r.cycle_length} s)`, r.cycle_length === timing.cycle_length],
    [`Every green is between ${r.constraints.min_green} and ${r.constraints.max_green} s`, r.greens.every((g) => g >= r.constraints.min_green && g <= r.constraints.max_green)], ["No constraint violation", r.constraints.violation_s === 0]];
  return (
    <div className="space-y-5">
      <Card title="Scenario and signal settings" subtitle="Saturation flow (3,600 PCU/h per phase) and the equal-split Fixed-Time plan are assumptions">
        <ScenarioPicker dataset={dataset} value={scenario} onChange={setScenario}>
          <Select label="Demand source" value={source} onChange={(e) => setSource(e.target.value)} options={[{ value: "predicted", label: "ML-predicted demand" }, { value: "observed", label: "Observed demand" }, { value: "manual", label: "Manual what-if (hypothetical)" }]} />
        </ScenarioPicker>
        {source === "manual" && <div className="mt-4"><p className="mb-1 text-sm font-medium">Hypothetical vehicles per hour <Tag kind="hypothetical" /></p><div className="grid gap-4 sm:grid-cols-4">
          {DIRECTIONS.map((d, i) => <NumberInput key={d} label={d} min={0} max={20000} value={manual[i]} onChange={(v) => setManual(manual.map((m, j) => (j === i ? v : m)))} />)}</div></div>}
        <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <NumberInput label="Cycle length (s)" min={20} max={300} value={timing.cycle_length} onChange={setT("cycle_length")} />
          <NumberInput label="Minimum green (s)" min={1} max={120} value={timing.min_green} onChange={setT("min_green")} />
          <NumberInput label="Maximum green (s)" min={1} max={240} value={timing.max_green} onChange={setT("max_green")} />
          <NumberInput label="Lost time per phase (s)" min={0} max={15} value={timing.lost_time} onChange={setT("lost_time")} hint="Yellow + all-red" />
        </div>
        <div className="mt-4"><Button variant="primary" icon={Cpu} busy={state.busy} disabled={!valid} onClick={run}>Optimize signal timings</Button></div>
      </Card>
      {state.error && <ErrorBox message={state.error} />}
      {!r && !state.error && <Empty icon={Cpu} title="No optimization yet" text="Pick a scenario and press Optimize. The Genetic Algorithm searches for green times that minimise estimated delay." />}
      {r && (<>
        {source === "manual" && <Note tone="warn">Hypothetical scenario: these demand values were typed in, they are not observed or predicted.</Note>}
        {r.predicted_pcu_h && DIRECTIONS.some((_, i) => Math.abs(r.predicted_pcu_h[i] - r.observed_pcu_h[i]) > 0.5 * Math.max(r.observed_pcu_h[i], 100)) && (
          <Note tone="warn">The ML-predicted demand differs from the observed demand by more than 50% in at least one direction. The model shrinks predictions toward the averages of its training clips, so it under-predicts heavy flows. Switch the demand source to "Observed demand" to compare.</Note>)}
        <Card title="Demand summary" tag={source === "manual" ? "hypothetical" : source === "predicted" ? "predicted" : "observed"} subtitle={r.demand_source}>
          <Table rows={DIRECTIONS.map((d, i) => ({ d, observed: r.observed_pcu_h[i], predicted: r.predicted_pcu_h?.[i], used: r.demand_pcu_h[i] }))} cols={[
            { h: "Direction", f: (x) => x.d }, { h: "Observed (PCU/h)", f: (x) => num(x.observed, 0), right: true }, { h: "ML-predicted (PCU/h)", f: (x) => (x.predicted == null ? "-" : num(x.predicted, 0)), right: true }, { h: "Used by GA (PCU/h)", f: (x) => num(x.used, 0), right: true }]} />
        </Card>
        <div className="grid gap-5 xl:grid-cols-2">
          <Card title="Signal-phase timing" tag="simulated" subtitle="Green time per phase; amber = lost time. Recommended plan, not a deployed one.">
            <PhaseBar title="Fixed-Time plan" greens={r.fixed_greens} lost={r.constraints.lost_time_per_phase} cycle={r.cycle_length} />
            <PhaseBar title="Optimized plan (Genetic Algorithm)" greens={r.greens} lost={r.constraints.lost_time_per_phase} cycle={r.cycle_length} />
            <ul className="mt-3 space-y-1 text-sm">{check.map(([t, ok]) => <li key={t} className="flex items-center gap-2">{ok ? <CheckCircle2 size={15} className="text-good" /> : <XCircle size={15} className="text-bad" />}{t}</li>)}</ul>
          </Card>
          <Card title="Estimated delay per vehicle" tag="simulated" subtitle={`HCM-style formula, not measured. Overall objective ${num(r.fixed_fitness)} -> ${num(r.fitness)} (${num(r.improvement_pct)}% lower)`}>
            <BarBox data={DIRECTIONS.map((d, i) => ({ d, Fixed: r.fixed[i].delay_s, Optimized: r.optimized[i].delay_s }))} xKey="d" yLabel="Delay (s per PCU)" series={[{ key: "Fixed", color: CTRL_COLORS.fixed }, { key: "Optimized", color: CTRL_COLORS.adaptive }]} />
          </Card>
        </div>
        <Card title="Why these timings?" tag="simulated">
          <ul className="list-disc space-y-2 pl-5 text-sm">{r.explanation.map((t) => <li key={t}>{t}</li>)}</ul>
          <Table rows={DIRECTIONS.map((d, i) => ({ d, f: r.fixed[i], o: r.optimized[i] }))} cols={[{ h: "Direction", f: (x) => x.d }, { h: "Green (s)", f: (x) => `${x.f.green_s} -> ${x.o.green_s}`, right: true },
            { h: "Saturation X", f: (x) => `${x.f.x} -> ${x.o.x}`, right: true }, { h: "Est. queue at end of red (PCU)", f: (x) => `${x.f.queue_pcu} -> ${x.o.queue_pcu}`, right: true }]} />
          <p className="mt-4 text-sm font-semibold">Limitations</p><ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-muted">{r.limitations.map((t) => <li key={t}>{t}</li>)}</ul>
        </Card></>)}
    </div>
  );
}
