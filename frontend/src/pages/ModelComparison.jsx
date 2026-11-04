import { Trophy } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client.js";
import { BarBox } from "../components/charts.jsx";
import { Card, ErrorBox, Note, Select, Skeleton, Table } from "../components/ui.jsx";
import { useApi } from "../hooks/useApi.js";
import { num } from "../utils.js";

const METRICS = [{ value: "mae", label: "MAE (lower is better)" }, { value: "rmse", label: "RMSE (lower is better)" }, { value: "r2", label: "R² (higher is better)" }];

export default function ModelComparison() {
  const [horizon, setHorizon] = useState(3);
  const [metric, setMetric] = useState("mae");
  const state = useApi(() => api.modelComparison(horizon), [horizon]);
  const d = state.data;
  const sign = metric === "r2" ? -1 : 1;
  const best = (rows) => rows.reduce((a, b) => (sign * (b[metric] ?? -sign * 1e9) < sign * (a[metric] ?? -sign * 1e9) ? b : a));
  return (
    <div className="space-y-5">
      <Card><div className="grid gap-4 sm:grid-cols-2">
        <Select label="Prediction horizon" value={horizon} options={[1, 2, 3, 4].map((h) => ({ value: h, label: `Next ${h} second${h > 1 ? "s" : ""}` }))} onChange={(e) => setHorizon(Number(e.target.value))} />
        <Select label="Selection metric" value={metric} options={METRICS} onChange={(e) => setMetric(e.target.value)} />
      </div></Card>
      {state.error ? <ErrorBox message={state.error} /> : !d ? <Skeleton className="h-72" /> : (
        <>
          <Note>Best on {metric.toUpperCase()}: <b>{best(d.models).name}</b>. Best trained ML model: <b>{best(d.models.filter((m) => m.kind === "model")).name}</b>.
            {best(d.models).kind === "baseline" && " A simple baseline wins this metric, so the ML models add little here (see the note below)."}</Note>
          <Card title="Test-set performance" tag="predicted" subtitle={`Evaluated on ${d.split.test.clips} held-out clips (${d.split.test.rows} samples) the models never saw. Trained on ${d.split.train.rows} samples from ${d.split.train.clips} earlier clips.`}>
            <Table rows={d.models} cols={[
              { h: "Model", f: (r) => <span className="flex items-center gap-2">{r.name}{r.name === best(d.models).name && <Trophy size={14} className="text-warn" aria-label="Best on selected metric" />}</span> },
              { h: "Type", f: (r) => (r.kind === "model" ? "ML model" : "Baseline") }, { h: "MAE", f: (r) => num(r.mae, 3), right: true }, { h: "RMSE", f: (r) => num(r.rmse, 3), right: true },
              { h: "R²", f: (r) => num(r.r2, 3), right: true }, { h: "Training status", f: (r) => <span className="text-muted">{r.status}</span> }]} />
          </Card>
          <Card title={`${metric.toUpperCase()} on the test set`} tag="predicted" subtitle="Bars show the selected metric for every model and baseline">
            <BarBox data={d.models.map((m) => ({ name: m.name.replace("Baseline: ", "Base: "), value: m[metric] }))} xKey="name" yLabel={metric.toUpperCase()} series={[{ key: "value", name: metric.toUpperCase(), color: "#22d3ee" }]} />
          </Card>
          <Note tone="warn">{d.note} MAE favours predicting "no vehicles", which is why the simple recent-rate baseline looks good on MAE while having negative R². Split: {d.split_method}. Trained {d.trained_at}.</Note>
        </>)}
    </div>
  );
}
