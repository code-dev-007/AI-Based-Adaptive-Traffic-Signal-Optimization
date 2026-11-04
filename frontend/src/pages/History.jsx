import { History as HistoryIcon, Trash2 } from "lucide-react";
import { useState } from "react";
import { api, errorMessage } from "../api/client.js";
import { BarBox } from "../components/charts.jsx";
import { Async, Button, Card, Empty, Note, Table, Tag, useToast } from "../components/ui.jsx";
import { useApi } from "../hooks/useApi.js";
import { CTRL_COLORS, num } from "../utils.js";

export default function History() {
  const toast = useToast();
  const [version, setVersion] = useState(0);
  const state = useApi(api.history, [version]);
  const [picked, setPicked] = useState([]);
  const [detail, setDetail] = useState(null);
  const [confirm, setConfirm] = useState(false);
  const toggle = (id) => setPicked(picked.includes(id) ? picked.filter((p) => p !== id) : [...picked, id]);
  const clear = async () => {
    try { const r = await api.clearHistory(); toast(`Deleted ${r.deleted} saved run(s).`); setConfirm(false); setPicked([]); setDetail(null); setVersion(version + 1); } catch (e) { toast(errorMessage(e), "error"); }
  };
  return (
    <Async state={state}>{({ items }) => {
      const label = (r) => `#${r.id} ${r.result.controller === "adaptive" ? "Adaptive" : "Fixed"}`;
      const chosen = items.filter((r) => picked.includes(r.id));
      const d = detail && items.find((r) => r.id === detail);
      return (
        <div className="space-y-5">
          <Card title="Saved experiments" tag="simulated" subtitle="Every Fixed-Time vs Adaptive run and finished live simulation is saved here automatically"
                actions={items.length > 0 && (confirm ? <span className="flex items-center gap-2 text-sm">Delete all {items.length} runs?<Button variant="danger" onClick={clear}>Yes, delete</Button><Button onClick={() => setConfirm(false)}>Cancel</Button></span>
                  : <Button icon={Trash2} onClick={() => setConfirm(true)}>Clear history</Button>)}>
            {!items.length ? <Empty icon={HistoryIcon} title="No experiments saved yet" text="Run an experiment on the Waiting-Time Analytics or Live Simulation page. Nothing is pre-filled here." /> : (
              <Table rows={items} cols={[
                { h: "Compare", f: (r) => <input type="checkbox" aria-label={`Select run ${r.id}`} checked={picked.includes(r.id)} onChange={() => toggle(r.id)} className="h-4 w-4 accent-cyan-400" /> },
                { h: "Experiment", f: (r) => r.result.name }, { h: "Scenario", f: (r) => `${r.scenario} x${r.result.multiplier}` },
                { h: "Controller", f: (r) => (r.result.controller === "adaptive" ? "Adaptive" : "Fixed-Time") }, { h: "Duration", f: (r) => `${r.result.duration_s} s`, right: true },
                { h: "Avg wait", f: (r) => `${num(r.result.metrics.avg_wait_s.mean)} s`, right: true }, { h: "Avg queue", f: (r) => `${num(r.result.metrics.avg_queue.mean)} veh`, right: true },
                { h: "Date", f: (r) => r.created_at.replace("T", " ") }, { h: "Details", f: (r) => <button className="font-semibold text-cyan hover:underline" onClick={() => setDetail(r.id)}>View</button> }]} />)}
          </Card>
          {chosen.length >= 2 && (
            <Card title="Comparison of selected runs" tag="simulated" subtitle="Compare only runs of the same scenario for a fair reading">
              <BarBox height={260} xKey="run" yLabel="Seconds / vehicles" series={[{ key: "Avg wait (s)", color: "#22d3ee" }, { key: "Avg queue (veh)", color: "#c98500" }, { key: "Max wait (s)", color: CTRL_COLORS.fixed }]}
                      data={chosen.map((r) => ({ run: label(r), "Avg wait (s)": +r.result.metrics.avg_wait_s.mean.toFixed(1), "Avg queue (veh)": +r.result.metrics.avg_queue.mean.toFixed(1), "Max wait (s)": +r.result.metrics.max_wait_s.mean.toFixed(1) }))} />
            </Card>)}
          {chosen.length === 1 && <Note>Select at least two runs to compare them.</Note>}
          {d && (
            <Card title={`Details: ${d.result.name}`} tag="simulated" actions={<Button onClick={() => setDetail(null)}>Close</Button>}>
              <div className="grid gap-5 lg:grid-cols-2">
                <Table rows={Object.entries(d.result.metrics)} cols={[{ h: "Metric", f: ([k]) => k }, { h: "Mean", f: ([, v]) => num(v.mean, 2), right: true }, { h: "Std dev", f: ([, v]) => num(v.std, 2), right: true }]} />
                <div className="space-y-2 text-sm"><Tag kind="assumption" />
                  <p><b>Saved:</b> {d.created_at.replace("T", " ")} ({d.kind === "simulation" ? "live simulation" : `${d.result.n_seeds} seeds from ${d.result.base_seed}`}).</p>
                  <p><b>Scenario:</b> {d.scenario}, period <code>{d.result.period}</code>, demand x{d.result.multiplier}.</p>
                  <p><b>Settings:</b> cycle {d.result.config.cycle_length} s, green {d.result.config.min_green}-{d.result.config.max_green} s, lost {d.result.config.lost_time} s, saturation {d.result.config.saturation_flow} PCU/h, Fixed-Time plan: {d.result.config.fixed_plan}.</p>
                  {d.result.fixed_greens && <p><b>Fixed-Time greens (UP/DOWN/RIGHT/LEFT):</b> {d.result.fixed_greens.join(" / ")}</p>}
                  {d.result.plans?.map((p) => <p key={p.t}><b>Adaptive re-plan at {p.t} s:</b> {p.greens.join(" / ")}</p>)}
                  {d.result.reduction && <p><b>Waiting-time change (Adaptive vs Fixed):</b> {d.result.reduction.wait_pct == null ? "n/a" : `${num(d.result.reduction.wait_pct)}% ${d.result.reduction.wait_pct >= 0 ? "lower" : "higher"}`}</p>}
                </div>
              </div>
            </Card>)}
        </div>);
    }}</Async>
  );
}
