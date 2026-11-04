import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const axis = { tick: { fill: "#8d9bb8", fontSize: 12 }, stroke: "#22304f" };
const tooltip = { contentStyle: { background: "#16223d", border: "1px solid #22304f", borderRadius: 8, color: "#e6edf7", fontSize: 12 }, labelStyle: { color: "#8d9bb8" }, cursor: { stroke: "#8d9bb8", fill: "rgba(141,155,184,0.08)" } };

// `series` items: { key, name?, color, dashed?, dots? }. Every chart has a legend, axis labels with units and a tooltip.
function Frame({ chart: Chart, data, xKey, height, xLabel, yLabel, xTick, tooltipFormat, children, layout }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <Chart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 4 }} layout={layout}>
        <CartesianGrid stroke="#22304f" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey={xKey} tickFormatter={xTick} minTickGap={24} height={xLabel ? 52 : 30} {...axis} label={xLabel ? { value: xLabel, position: "insideBottom", offset: 0, fill: "#8d9bb8", fontSize: 12 } : undefined} />
        <YAxis {...axis} width={56} label={yLabel ? { value: yLabel, angle: -90, position: "insideLeft", fill: "#8d9bb8", fontSize: 12, style: { textAnchor: "middle" } } : undefined} />
        <Tooltip {...tooltip} formatter={tooltipFormat} />
        <Legend wrapperStyle={{ fontSize: 12, color: "#8d9bb8", paddingTop: 4 }} />
        {children}
      </Chart>
    </ResponsiveContainer>
  );
}

export const LineBox = ({ series, ...rest }) => (
  <Frame chart={LineChart} {...rest} height={rest.height ?? 280}>
    {series.map((s) => <Line key={s.key} type="linear" dataKey={s.key} name={s.name ?? s.key} stroke={s.color} strokeWidth={2} strokeDasharray={s.dashed ? "6 4" : undefined}
                             dot={s.dots ? { r: 3, strokeWidth: 0, fill: s.color } : false} activeDot={{ r: 5 }} isAnimationActive={false} connectNulls={false} />)}
  </Frame>
);

export const BarBox = ({ series, stacked, ...rest }) => (
  <Frame chart={BarChart} {...rest} height={rest.height ?? 280}>
    {series.map((s) => <Bar key={s.key} dataKey={s.key} name={s.name ?? s.key} fill={s.color} stackId={stacked ? "a" : undefined} radius={stacked ? 0 : [4, 4, 0, 0]} maxBarSize={48} stroke="#101a30" strokeWidth={stacked ? 2 : 0} isAnimationActive={false} />)}
  </Frame>
);
