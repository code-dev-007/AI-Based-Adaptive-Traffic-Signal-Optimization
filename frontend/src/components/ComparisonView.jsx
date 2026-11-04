import { Gauge, Timer, TrendingDown, Users } from "lucide-react";
import { CTRL_COLORS, DIRECTIONS, num } from "../utils.js";
import { BarBox } from "./charts.jsx";
import { Card, Note, Stat, Table } from "./ui.jsx";

const ROWS = [["Average waiting time", "avg_wait_s", "s"], ["Maximum waiting time", "max_wait_s", "s"], ["Average queue length", "avg_queue", "veh"], ["Maximum queue length", "max_queue", "veh"],
  ["Vehicles served", "served", "veh"], ["Throughput", "throughput_vph", "veh/h"], ["Congested time", "congestion_pct", "%"]];
/** Waiting-time reduction (%) = (Fixed - Adaptive) / Fixed x 100. A negative value means Adaptive was WORSE and is shown as such. */
const change = (v, noun) => (v == null ? "n/a: Fixed-Time value is 0" : v >= 0 ? `${num(v)}% lower ${noun}` : `${num(-v)}% higher ${noun} (Adaptive worse)`);
const tone = (v) => (v == null ? "cyan" : v >= 0 ? "good" : "bad");

/** Results of one Fixed-Time vs Adaptive experiment (the /experiments response). All values are simulated. */
export default function ComparisonView({ r }) {
  const { summary: s, reduction: red } = r;
  const m = (c, k) => s[c][k].mean;
  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Waiting-time reduction" icon={Timer} tone={tone(red.wait_pct)} tag="simulated" value={red.wait_pct == null ? "n/a" : num(red.wait_pct)} unit="%" sub={change(red.wait_pct, "waiting time")} />
        <Stat label="Queue-length reduction" icon={Users} tone={tone(red.queue_pct)} tag="simulated" value={red.queue_pct == null ? "n/a" : num(red.queue_pct)} unit="%" sub={change(red.queue_pct, "average queue")} />
        <Stat label="Congestion reduction" icon={TrendingDown} tone={tone(red.congestion_pct)} tag="simulated" value={red.congestion_pct == null ? "n/a" : num(red.congestion_pct)} unit="%" sub={change(red.congestion_pct, "congested time")} />
        <Stat label="Throughput change" icon={Gauge} tone={red.throughput_change_pct >= 0 ? "good" : "bad"} tag="simulated" value={red.throughput_change_pct == null ? "n/a" : num(red.throughput_change_pct)} unit="%" sub="Vehicles served per hour, Adaptive vs Fixed-Time" />
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <Card title="Fixed-Time vs Adaptive" tag="simulated" subtitle={`Mean of ${r.n_seeds} seeds; both controllers see identical arrivals`}>
          <Table rows={ROWS} cols={[{ h: "Metric", f: (x) => x[0] }, { h: "Fixed-Time", f: (x) => `${num(m("fixed", x[1]))} ${x[2]}`, right: true }, { h: "Adaptive", f: (x) => `${num(m("adaptive", x[1]))} ${x[2]}`, right: true },
            { h: "Std dev (F / A)", f: (x) => `${num(s.fixed[x[1]].std)} / ${num(s.adaptive[x[1]].std)}`, right: true }]} />
        </Card>
        <Card title="Waiting time and queue length" tag="simulated" subtitle="Lower is better">
          <BarBox height={250} xKey="metric" yLabel="Seconds / vehicles" series={[{ key: "Fixed-Time", color: CTRL_COLORS.fixed }, { key: "Adaptive", color: CTRL_COLORS.adaptive }]}
                  data={[["Avg wait (s)", "avg_wait_s"], ["Max wait (s)", "max_wait_s"], ["Avg queue (veh)", "avg_queue"], ["Max queue (veh)", "max_queue"]].map(([metric, k]) => ({ metric, "Fixed-Time": +m("fixed", k).toFixed(1), Adaptive: +m("adaptive", k).toFixed(1) }))} />
        </Card>
        <Card title="Average wait by direction" tag="simulated" subtitle="First seed. Shows who gains and who loses green time">
          <BarBox height={250} xKey="direction" yLabel="Seconds" series={[{ key: "Fixed-Time", color: CTRL_COLORS.fixed }, { key: "Adaptive", color: CTRL_COLORS.adaptive }]}
                  data={DIRECTIONS.map((d, i) => ({ direction: d, "Fixed-Time": +r.examples.fixed.metrics.by_direction[i].avg_wait_s.toFixed(1), Adaptive: +r.examples.adaptive.metrics.by_direction[i].avg_wait_s.toFixed(1) }))} />
        </Card>
        <Card title="Signal plans used" tag="simulated" subtitle="Green seconds for UP / DOWN / RIGHT / LEFT">
          <p className="text-sm">Fixed-Time: <b>{r.fixed_greens.join(" / ")}</b></p>
          <ul className="mt-2 space-y-1 text-sm text-muted">{r.examples.adaptive.plans.map((p) => <li key={p.t}>Adaptive re-plan at {p.t} s: <b className="text-ink">{p.greens.join(" / ")}</b></li>)}
            {!r.examples.adaptive.plans.length && <li>The Adaptive controller never re-planned (duration shorter than one re-plan interval).</li>}</ul>
          <Note>Waiting time counts every arrived vehicle, including those still queued at the end. If demand exceeds capacity, queues keep growing and waits depend on the run length.</Note>
        </Card>
      </div>
    </div>
  );
}
