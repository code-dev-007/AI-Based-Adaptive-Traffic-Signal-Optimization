import { CalendarDays, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client.js";
import { BarBox, LineBox } from "../components/charts.jsx";
import { Async, Card, Note, Select, Stat, Table, Tip } from "../components/ui.jsx";
import { useApi } from "../hooks/useApi.js";
import { CLASSES, CLASS_COLORS, DIRECTIONS, DIR_COLORS, LEVEL_STYLE, num } from "../utils.js";

const LINE_COLORS = ["#3987e5", "#d95926", "#199e70"];
const short = (j) => j.replace("Chowk", "");
const when = (r) => `${r.date} (${r.weekday.slice(0, 3)}), clips start ${r.first_clip_start}-${r.last_clip_start}`;

export default function PeakHour() {
  const state = useApi(api.peak);
  return <Async state={state}>{(d) => <View data={d} />}</Async>;
}

function View({ data }) {
  const [junction, setJunction] = useState("all");
  const [direction, setDirection] = useState("all");
  const [date, setDate] = useState("all");
  const junctions = junction === "all" ? data.junctions : [junction];
  const dirs = direction === "all" ? DIRECTIONS : [direction];
  const dated = data.by_date.filter((r) => junctions.includes(r.junction) && (date === "all" || r.date === date));
  const minutes = [...new Set(data.by_minute.map((m) => m.time))].sort();
  const lineData = minutes.map((time) => ({ time, ...Object.fromEntries(junctions.map((j) => [j, data.by_minute.find((m) => m.junction === j && m.time === time && m.level !== "insufficient")?.rate_vph ?? null])) }));
  const dateChart = data.dates.map((d) => ({ date: d.slice(5), ...Object.fromEntries(junctions.map((j) => [short(j), data.by_date.find((r) => r.junction === j && r.date === d)?.vehicles])) }));
  const dirData = junctions.map((j) => ({ junction: short(j), ...Object.fromEntries(dirs.map((d) => [d, data.by_direction.find((r) => r.junction === j && r.direction === d)?.rate_vph])) }));
  const classData = junctions.map((j) => ({ junction: short(j), ...Object.fromEntries(CLASSES.map((c) => [c, data.by_junction.find((r) => r.junction === j)[c]])) }));
  const winNames = [...new Set(data.windows.map((w) => w.window))];
  const busiest = data.busiest_windows.filter((r) => junctions.includes(r.junction));
  const top = data.busiest_overall;
  return (
    <div className="space-y-5">
      <Note><b>Method:</b> {data.method} <Tip text="Observed counts are what the video clips contain. Hourly-equivalent rates extrapolate seconds of video to one hour, so they are estimates only.">Observed vs estimated</Tip></Note>
      <Card><div className="grid gap-4 sm:grid-cols-3">
        <Select label="Junction" value={junction} options={[{ value: "all", label: "All junctions" }, ...data.junctions]} onChange={(e) => setJunction(e.target.value)} />
        <Select label="Date (date-wise table)" value={date} options={[{ value: "all", label: "All dates" }, ...data.dates]} onChange={(e) => setDate(e.target.value)} />
        <Select label="Direction (direction chart)" value={direction} options={[{ value: "all", label: "All directions" }, ...DIRECTIONS]} onChange={(e) => setDirection(e.target.value)} />
      </div></Card>
      <div className="grid gap-4 md:grid-cols-3">{busiest.map((r) => (
        <Stat key={r.junction} label={`${r.junction}: busiest observed window`} icon={CalendarDays} tone="warn" tag="estimated" value={num(r.rate_vph, 0)} unit="veh/h (estimate)"
              sub={`${when(r)}. Observed: ${r.vehicles} vehicles in ${r.sampled_s} s of video, window ${r.window}.${r.caution ? ` Caution: one clip holds ${r.top_clip_pct}% of them.` : ""}`} />))}</div>
      {top && <p className="text-sm text-muted">Busiest observed window overall: <b className="text-ink">{short(top.junction)}, {top.date} ({top.weekday}), clips starting {top.first_clip_start}-{top.last_clip_start}</b>. It is the highest value in the available video samples, not a city-wide rush hour.</p>}
      <div className="grid gap-5 xl:grid-cols-2">
        <Card title="Observed vehicles per date" subtitle="Total counted in that day's recorded clips (video time differs per day and junction)" tag="observed">
          <BarBox data={dateChart} xKey="date" xLabel="Date (MM-DD, 2023)" yLabel="Vehicles counted" series={junctions.map((j) => ({ key: short(j), color: LINE_COLORS[data.junctions.indexOf(j) % 3] }))} />
        </Card>
        <Card title="Vehicle classes" subtitle="Vehicles counted per class, all dates" tag="aggregated">
          <BarBox data={classData} xKey="junction" yLabel="Vehicles counted" stacked series={CLASSES.map((c) => ({ key: c, color: CLASS_COLORS[c] }))} />
        </Card>
        <Card title="Traffic by direction" subtitle="Estimated hourly-equivalent rate, all dates" tag="aggregated">
          <BarBox data={dirData} xKey="junction" yLabel="Estimated vehicles per hour" series={dirs.map((d) => ({ key: d, color: DIR_COLORS[d] }))} />
        </Card>
        <Card title="Window A vs Window B" subtitle="Clock windows (clips of all dates that start in each window), estimated rate" tag="aggregated">
          <BarBox data={junctions.map((j) => ({ junction: short(j), ...Object.fromEntries(data.windows.filter((w) => w.junction === j).map((w) => [w.window.slice(0, 8), w.rate_vph])) }))} xKey="junction" yLabel="Estimated vehicles per hour"
                  series={winNames.map((w, i) => ({ key: w.slice(0, 8), color: i ? "#c98500" : "#3987e5" }))} />
        </Card>
      </div>
      <Card title="Traffic by clock minute" subtitle="Only minutes with at least 3 clips are plotted. Clips of different dates that start in the same minute are pooled here" tag="aggregated">
        <LineBox data={lineData} xKey="time" xLabel="Clock time (minute)" yLabel="Estimated vehicles per hour" series={junctions.map((j, i) => ({ key: j, color: LINE_COLORS[data.junctions.indexOf(j) % 3] ?? LINE_COLORS[i], dots: true }))} />
      </Card>
      <Card title="Date-wise observations" subtitle="One row per junction and date. Dates are never merged in this table" tag="observed">
        <Table rows={dated} cols={[
          { h: "Junction", f: (r) => short(r.junction) }, { h: "Date", f: (r) => `${r.date} ${r.weekday.slice(0, 3)}` }, { h: "Cameras", f: (r) => r.cameras.join(", ") }, { h: "Clips", f: (r) => r.clips, right: true },
          { h: "Clip starts", f: (r) => `${r.first_clip_start}-${r.last_clip_start}` }, { h: "Video (s)", f: (r) => r.sampled_s, right: true }, { h: "Vehicles", f: (r) => r.vehicles, right: true },
          { h: "Est. rate (veh/h)", f: (r) => num(r.rate_vph, 0), right: true }]} />
      </Card>
      <Card title="Clock-minute levels" subtitle="Heavy / light / moderate relative to the junction's own average (estimated rates)" tag="aggregated">
        <Table rows={data.by_minute.filter((m) => junctions.includes(m.junction))} cols={[
          { h: "Junction", f: (r) => short(r.junction) }, { h: "Minute", f: (r) => r.time }, { h: "Dates", f: (r) => r.dates, right: true }, { h: "Clips", f: (r) => r.clips, right: true }, { h: "Video (s)", f: (r) => r.sampled_s, right: true },
          { h: "Vehicles", f: (r) => r.vehicles, right: true }, { h: "Est. rate (veh/h)", f: (r) => num(r.rate_vph, 0), right: true }, { h: "x average", f: (r) => r.intensity, right: true },
          { h: "Level", f: (r) => <span className={`rounded px-2 py-0.5 text-xs font-semibold ${LEVEL_STYLE[r.level]}`}>{r.level}</span> }]} />
      </Card>
      <Card title="Data limitations"><ul className="grid gap-3 text-sm md:grid-cols-2">{data.limitations.map((l) => (
        <li key={l.title} className="flex gap-2 rounded-lg border border-warn/30 bg-warn/10 p-3"><TriangleAlert size={16} className="mt-0.5 shrink-0 text-warn" /><span><b className="text-warn">{l.title}:</b> <span className="text-muted">{l.text}</span></span></li>))}</ul>
        {data.rows_without_verified_date > 0 && <p className="mt-3 text-sm text-warn">{data.rows_without_verified_date} rows had no verifiable date and are excluded.</p>}
      </Card>
    </div>
  );
}
