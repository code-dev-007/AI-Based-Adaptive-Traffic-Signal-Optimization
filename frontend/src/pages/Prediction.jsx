import { Gauge, Sigma, Target } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client.js";
import { LineBox } from "../components/charts.jsx";
import { Async, Card, Note, Select, Skeleton, Stat, Table, Tip, ErrorBox } from "../components/ui.jsx";
import { useApi } from "../hooks/useApi.js";
import { DIRECTIONS, num } from "../utils.js";

export default function Prediction() {
  const dataset = useApi(api.dataset);
  return <Async state={dataset}>{(d) => <View junctions={d.report.junctions} />}</Async>;
}

function View({ junctions }) {
  const [sel, setSel] = useState({ junction: junctions[0], direction: "DOWN", horizon: 3 });
  const result = useApi(() => api.predict(sel), [sel.junction, sel.direction, sel.horizon]);
  const d = result.data;
  const rows = d?.items.map((r, i) => ({ ...r, i, label: `${r.clip.replace(".csv", "")} @${r.second}s`, error: Math.abs(r.actual - r.predicted) }));
  return (
    <div className="space-y-5">
      <Card><div className="grid gap-4 sm:grid-cols-3">
        <Select label="Junction" value={sel.junction} options={junctions} onChange={(e) => setSel({ ...sel, junction: e.target.value })} />
        <Select label="Direction" value={sel.direction} options={DIRECTIONS} onChange={(e) => setSel({ ...sel, direction: e.target.value })} />
        <Select label="Prediction horizon" value={sel.horizon} options={[1, 2, 3, 4].map((h) => ({ value: h, label: `Next ${h} second${h > 1 ? "s" : ""}` }))} onChange={(e) => setSel({ ...sel, horizon: Number(e.target.value) })} />
      </div></Card>
      {result.error ? <ErrorBox message={result.error} /> : (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <Stat label="MAE (this selection)" icon={Target} loading={!d} value={num(d?.metrics.mae, 3)} unit="veh" tag="predicted" sub={`Whole test set: ${num(d?.overall_test_metrics.mae, 3)}`} />
            <Stat label="RMSE (this selection)" icon={Sigma} loading={!d} value={num(d?.metrics.rmse, 3)} unit="veh" tag="predicted" sub={`Whole test set: ${num(d?.overall_test_metrics.rmse, 3)}`} />
            <Stat label="R² (this selection)" icon={Gauge} tone="warn" loading={!d} value={num(d?.metrics.r2, 3)} tag="predicted" sub={`Whole test set: ${num(d?.overall_test_metrics.r2, 3)}`} />
          </div>
          <Note tone="warn">Arrivals over a few seconds are mostly zero and highly random, so R² is low for every model. Metrics are on held-out clips only (see Model Comparison for baselines).</Note>
          <Card title="Actual vs predicted arrivals" tag="predicted" subtitle={d?.note}>
            {!d ? <Skeleton className="h-72" /> : (
              <LineBox data={rows} xKey="i" xTick={(i) => rows[i]?.label ?? ""} xLabel="Held-out clip and second (chronological)" yLabel={`Vehicles in next ${sel.horizon} s`}
                       series={[{ key: "actual", name: "Actual (observed)", color: "#e6edf7", dots: true }, { key: "predicted", name: "Predicted (XGBoost)", color: "#22d3ee", dashed: true, dots: true }]} />)}
          </Card>
          <Card title="Prediction results" subtitle="Most recent held-out samples first. Solid white = observed, dashed cyan = prediction."
                tag="predicted">
            {!d ? <Skeleton className="h-40" /> : <div className="max-h-80 overflow-y-auto"><Table rows={[...rows].reverse().slice(0, 60)} cols={[
              { h: "Clip", f: (r) => r.clip }, { h: "Second", f: (r) => r.second, right: true }, { h: "Actual (veh)", f: (r) => r.actual, right: true },
              { h: "Predicted (veh)", f: (r) => num(r.predicted, 2), right: true }, { h: <Tip text="Absolute error = |actual - predicted|">Abs. error</Tip>, f: (r) => num(r.error, 2), right: true }]} /></div>}
          </Card>
        </>)}
    </div>
  );
}
