import { Car, CheckCircle2, Clock, Database, ExternalLink, MapPin, Timer, TriangleAlert } from "lucide-react";
import { api } from "../api/client.js";
import { BarBox, LineBox } from "../components/charts.jsx";
import { Async, Card, ErrorBox, Note, Skeleton, Stat, Table, Tag } from "../components/ui.jsx";
import { useApi } from "../hooks/useApi.js";
import { CLASSES, CLASS_COLORS, CTRL_COLORS, DIRECTIONS, DIR_COLORS, num } from "../utils.js";

const Chart = ({ title, subtitle, state, children, tag = "observed" }) => (
  <Card title={title} subtitle={subtitle} tag={tag}>{state.loading ? <Skeleton className="h-64" /> : state.error ? <ErrorBox message={state.error} /> : children(state.data)}</Card>
);

const Check = ({ label, children }) => (
  <li className="flex gap-2 text-sm"><CheckCircle2 size={16} className="mt-0.5 shrink-0 text-good" /><span><span className="font-medium text-ink">{label}</span> <span className="text-muted">{children}</span></span></li>
);

function QualityReport({ r }) {
  const src = r.source, bad = Object.values(r.invalid_rows).reduce((a, b) => a + b, 0);
  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-line bg-raised p-4 text-sm">
        <div className="flex flex-wrap items-center gap-2"><span className="font-semibold text-ink">{src.name}</span><span className="rounded-md bg-good/15 px-2 py-0.5 text-[11px] font-semibold text-good">Documented source</span></div>
        <dl className="mt-3 grid gap-x-6 gap-y-2 text-muted sm:grid-cols-2">
          <div><dt className="text-xs uppercase tracking-wide">Published by</dt><dd className="text-ink">{src.publisher}</dd></div>
          <div><dt className="text-xs uppercase tracking-wide">Contributors</dt><dd className="text-ink">{src.contributors}</dd></div>
          <div><dt className="text-xs uppercase tracking-wide">DOI</dt><dd className="text-ink">{src.doi}</dd></div>
          <div><dt className="text-xs uppercase tracking-wide">License</dt><dd className="text-ink">{src.license}</dd></div>
          <div><dt className="text-xs uppercase tracking-wide">Collection period</dt><dd className="text-ink">{src.collection_period}</dd></div>
          <div><dt className="text-xs uppercase tracking-wide">Records used here</dt><dd className="text-ink">{num(src.selected_records, 0)} selected records</dd></div>
        </dl>
        <a href={src.url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-cyan hover:underline"><ExternalLink size={14} />{src.url}</a>
        <p className="mt-3 text-muted">{src.subset_note}</p>
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <ul className="space-y-2.5">
          <Check label="Records:">{num(r.rows_in, 0)} read, {num(r.rows_valid, 0)} valid, {bad} invalid, {r.missing_values} missing values{r.matches_expected_100000 ? " (exactly 100,000)" : ""}.</Check>
          <Check label="Date:">derived from the source filenames; {r.dates} days, {r.first_date} to {r.last_date}.</Check>
          <Check label="Time:">start timestamp of the aggregation interval, {r.first_time} to {r.last_time}.</Check>
          <Check label="Direction:">{r.directions.join(", ")} are the documented vehicle movement directions through the junction.</Check>
          <Check label="Counts:">{r.notes.count_handling}</Check>
          <Check label="Repeated rows:">{r.notes.duplicates} ({num(r.exact_duplicate_rows, 0)} rows)</Check>
        </ul>
        <Table rows={[["Junctions", r.junctions.join(", ")], ["Cameras", r.cameras.join(", ")], ["Source files (clips)", r.clips],
          ["Footage covered", `${num(r.total_clip_seconds, 0)} s`], ["Vehicles counted", num(r.total_vehicles, 0)],
          ["By class", Object.entries(r.vehicles_by_class).map(([k, v]) => `${k} ${v}`).join(", ")]]} cols={[{ h: "Statistic", f: (x) => x[0] }, { h: "Value", f: (x) => x[1] }]} />
      </div>
      {r.limitations.map((l) => (
        <div key={l.title} className="flex gap-3 rounded-xl border border-warn/40 bg-warn/10 p-4 text-sm">
          <TriangleAlert size={18} className="mt-0.5 shrink-0 text-warn" />
          <div><div className="font-semibold text-warn">{l.title}</div><p className="mt-0.5 text-muted">{l.text}</p></div>
        </div>))}
    </div>
  );
}

export default function Dashboard({ goTo }) {
  const dataset = useApi(api.dataset);
  const peak = useApi(api.peak);
  const sim = useApi(api.dashboardSim);
  const report = dataset.data?.report;
  const s = sim.data?.summary;
  const perJunction = (rows, key) => peak.data.junctions.map((j) => ({ junction: j.replace("Chowk", ""), ...Object.fromEntries(rows.filter((r) => r.junction === j).map(key)) }));
  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Total valid traffic records" icon={Database} loading={!report} value={num(report?.rows_valid, 0)} unit="rows" tag="observed"
              sub={report?.matches_expected_100000 ? "All 100,000 rows valid; one row = one video frame" : "Row count differs from the expected 100,000"} tone={report?.matches_expected_100000 ? "good" : "warn"} />
        <Stat label="Junctions" icon={MapPin} loading={!report} value={report?.junctions.length} tag="observed" sub={`${report?.clips} video clips, ${num(report?.total_clip_seconds, 0)} s of footage`} />
        <Stat label="Peak traffic period" icon={Clock} tone="warn" loading={!peak.data} value={peak.data?.overall_peak?.time ?? "n/a"} unit="clock minute" tag="observed"
              sub={peak.data?.overall_peak ? `Busiest at ${peak.data.overall_peak.junctions} of ${peak.data.overall_peak.of} junctions` : "Not enough clips"} />
        <Stat label="Avg simulated waiting time" icon={Timer} loading={!s} value={s ? num(s.adaptive.avg_wait_s.mean, 0) : ""} unit="s Adaptive" tag="simulated"
              sub={s ? `Fixed-Time ${num(s.fixed.avg_wait_s.mean, 0)} s, ${sim.data.junction}` : sim.error ?? ""} tone="good" />
      </div>
      <Note>All dashboard values are computed live by the backend from the Pune CSV or from simulation runs. Waiting times are <b>simulated estimates</b>, not field measurements.</Note>
      <div className="grid gap-5 xl:grid-cols-2">
        <Chart title="Hourly traffic volume" subtitle="Rate by clock hour of the clips. No video was sampled in hours without a point." state={peak}>
          {(d) => <LineBox data={d.by_hour.map((h) => ({ hour: `${String(h.hour).padStart(2, "0")}:00`, rate: h.rate_vph, clips: h.clips }))} xKey="hour" xLabel="Clock hour (all days pooled)" yLabel="Vehicles per hour-equivalent"
                           series={[{ key: "rate", name: "Observed rate", color: "#22d3ee", dots: true }]} tooltipFormat={(v, n, p) => [`${num(v, 0)} veh/h (${p.payload.clips} clips)`, n]} />}
        </Chart>
        <Chart title="Peak vs off-peak" subtitle="Average rate of heavy minutes, light minutes and all minutes per junction" state={peak}>
          {(d) => <BarBox data={d.peak_vs_offpeak.map((r) => ({ junction: r.junction.replace("Chowk", ""), Peak: r.peak_rate_vph, "Off-peak": r.offpeak_rate_vph, Average: r.average_rate_vph }))} xKey="junction" yLabel="Vehicles per hour-equivalent"
                           tooltipFormat={(v, n) => [`${num(v, 0)} veh/h`, n]}
                           series={[{ key: "Peak", color: "#f59e0b" }, { key: "Off-peak", color: "#22d3ee" }, { key: "Average", color: "#94a3b8" }]} />}
        </Chart>
        <Chart title="Junction-wise traffic distribution" subtitle="Vehicles counted per direction in all sampled clips" state={peak}>
          {(d) => <BarBox stacked data={perJunction(d.by_direction, (r) => [r.direction, r.vehicles])} xKey="junction" yLabel="Vehicles counted"
                           series={DIRECTIONS.map((k) => ({ key: k, color: DIR_COLORS[k] }))} />}
        </Chart>
        <Chart title="Vehicle category distribution" subtitle="Share of vehicles by category at each junction" state={peak}>
          {(d) => <BarBox stacked data={d.by_junction.map((j) => ({ junction: j.junction.replace("Chowk", ""), ...Object.fromEntries(CLASSES.map((c) => [c, +(100 * j[c] / j.vehicles).toFixed(1)])) }))}
                           xKey="junction" yLabel="Share of vehicles (%)" series={CLASSES.map((k) => ({ key: k, color: CLASS_COLORS[k] }))} />}
        </Chart>
      </div>
      <Card title="Fixed-Time vs Adaptive (default scenario)" tag="simulated"
            subtitle={sim.data ? `${sim.data.junction}, all sampled clips, ${sim.data.duration_s / 60} min, ${sim.data.n_seeds} seeds` : "Running the default simulation..."}
            actions={<button onClick={() => goTo("analytics")} className="text-sm font-semibold text-cyan hover:underline">Run your own scenario</button>}>
        {sim.error ? <ErrorBox message={sim.error} /> : !s ? <Skeleton className="h-56" /> : (
          <div className="grid gap-4 lg:grid-cols-2">
            <BarBox height={240} xKey="metric" yLabel="Seconds / vehicles" series={[{ key: "Fixed-Time", color: CTRL_COLORS.fixed }, { key: "Adaptive", color: CTRL_COLORS.adaptive }]}
                    data={[["Avg wait (s)", "avg_wait_s"], ["Avg queue (veh)", "avg_queue"], ["Max wait (s)", "max_wait_s"]].map(([metric, k]) => ({ metric, "Fixed-Time": +s.fixed[k].mean.toFixed(1), Adaptive: +s.adaptive[k].mean.toFixed(1) }))} />
            <div className="flex flex-col justify-center gap-2 text-sm">
              <p>Waiting-time change: <b className={sim.data.reduction.wait_pct >= 0 ? "text-good" : "text-bad"}>{sim.data.reduction.wait_pct == null ? "n/a" : `${num(sim.data.reduction.wait_pct)}% ${sim.data.reduction.wait_pct >= 0 ? "reduction" : "increase (Adaptive was worse)"}`}</b></p>
              <p className="text-muted">Computed from real simulation runs on identical arrivals. See Waiting-Time Analytics for peak vs off-peak scenarios.</p><Tag kind="simulated" />
            </div>
          </div>)}
      </Card>
      <Card title="Data Quality Report" tag="observed" subtitle="Computed by the preprocessing pipeline from the untouched CSV (also saved in data/processed/data_quality_report.json)">
        {!report ? <Skeleton className="h-40" /> : <QualityReport r={report} />}
      </Card>
    </div>
  );
}
