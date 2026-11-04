import { BarChart3 } from "lucide-react";
import { useState } from "react";
import { api, errorMessage } from "../api/client.js";
import { BarBox } from "../components/charts.jsx";
import ComparisonView from "../components/ComparisonView.jsx";
import ScenarioPicker, { initialScenario } from "../components/ScenarioPicker.jsx";
import { Async, Button, Card, Empty, ErrorBox, NumberInput, Skeleton, useToast } from "../components/ui.jsx";
import { useApi } from "../hooks/useApi.js";
import { useSettings } from "../hooks/useSettings.js";
import { CTRL_COLORS, num } from "../utils.js";

export default function Analytics() {
  const dataset = useApi(api.dataset);
  return <Async state={dataset}>{(d) => <View dataset={d} />}</Async>;
}

function View({ dataset }) {
  const { settings } = useSettings();
  const toast = useToast();
  const [scenario, setScenario] = useState(initialScenario(dataset));
  const [opts, setOpts] = useState({ duration: 1800, n_seeds: 3, base_seed: 42 });
  const [state, setState] = useState({ results: [], busy: false, error: null });
  const valid = Object.values(opts).every((v) => v !== "");
  const run = async (periods) => {
    setState({ results: [], busy: true, error: null });
    try {
      const results = [];
      for (const [period, label] of periods) results.push({ label, data: await api.experiment({ ...settings, ...scenario, ...opts, period }) });
      setState({ results, busy: false, error: null });
      toast(`${results.length} experiment${results.length > 1 ? "s" : ""} finished and saved to Experiment History.`);
    } catch (e) { setState({ results: [], busy: false, error: errorMessage(e) }); toast(errorMessage(e), "error"); }
  };
  const set = (k) => (v) => setOpts({ ...opts, [k]: v });
  const both = state.results.length === 2;
  return (
    <div className="space-y-5">
      <Card title="Experiment setup" subtitle="Runs both controllers on identical simulated arrivals and saves the results to the database">
        <ScenarioPicker dataset={dataset} value={scenario} onChange={setScenario}>
          <NumberInput label="Duration (s)" min={60} max={7200} step={60} value={opts.duration} onChange={set("duration")} />
          <NumberInput label="Number of seeds" min={1} max={10} value={opts.n_seeds} onChange={set("n_seeds")} hint="More seeds, steadier averages" />
          <NumberInput label="Base random seed" min={0} max={999999} value={opts.base_seed} onChange={set("base_seed")} hint="Same seed, same result" />
        </ScenarioPicker>
        <div className="mt-4 flex flex-wrap gap-3">
          <Button variant="primary" icon={BarChart3} busy={state.busy} disabled={!valid} onClick={() => run([[scenario.period, "Selected period"]])}>Run Fixed-Time vs Adaptive</Button>
          <Button busy={state.busy} disabled={!valid} onClick={() => run([["peak", "Peak"], ["off_peak", "Off-peak"]])}>Run peak vs off-peak</Button>
        </div>
      </Card>
      {state.error && <ErrorBox message={state.error} />}
      {state.busy && <Skeleton className="h-64" />}
      {!state.busy && !state.results.length && !state.error && <Empty icon={BarChart3} title="No experiment run yet" text="Choose a scenario and run it. Results come from the simulator, nothing is pre-filled." />}
      {both && (
        <Card title="Peak vs off-peak performance" tag="simulated" subtitle="Average simulated waiting time. Peak and off-peak minutes are detected from the data (see Peak-Hour Analysis)">
          <BarBox height={240} xKey="period" yLabel="Average wait (s)" series={[{ key: "Fixed-Time", color: CTRL_COLORS.fixed }, { key: "Adaptive", color: CTRL_COLORS.adaptive }]}
                  data={state.results.map((r) => ({ period: r.label, "Fixed-Time": +r.data.summary.fixed.avg_wait_s.mean.toFixed(1), Adaptive: +r.data.summary.adaptive.avg_wait_s.mean.toFixed(1) }))} />
          <p className="mt-2 text-sm text-muted">{state.results.map((r) => `${r.label}: ${r.data.reduction.wait_pct == null ? "n/a" : `${num(r.data.reduction.wait_pct)}%`}`).join("   |   ")} change in waiting time</p>
        </Card>)}
      {state.results.map((r) => <section key={r.label} className="space-y-3">{both && <h2 className="text-lg font-semibold">{r.label}: {r.data.scenario}</h2>}<ComparisonView r={r.data} /></section>)}
    </div>
  );
}
