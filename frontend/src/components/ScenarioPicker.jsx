import { NumberInput, Select } from "./ui.jsx";

/** Junction + time period (only periods the data supports) + demand multiplier. `value` = { junction, period, multiplier }. */
export default function ScenarioPicker({ dataset, value, onChange, children }) {
  const junctions = dataset.report.junctions;
  const periods = dataset.periods[value.junction] ?? [];
  const set = (patch) => onChange({ ...value, ...patch });
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Select label="Junction" value={value.junction} options={junctions} onChange={(e) => set({ junction: e.target.value, period: "all" })} />
      <Select label="Observed period" value={value.period} options={periods.map((p) => ({ value: p.id, label: `${p.label} (${p.clips} clips)` }))} onChange={(e) => set({ period: e.target.value })} />
      <NumberInput label="Demand multiplier" min={0.1} max={5} step={0.1} value={value.multiplier} onChange={(v) => set({ multiplier: v })} hint="What-if scaling of observed demand (assumption)" />
      {children}
    </div>
  );
}

export const initialScenario = (dataset) => ({ junction: dataset.report.junctions[0], period: "all", multiplier: 1 });
