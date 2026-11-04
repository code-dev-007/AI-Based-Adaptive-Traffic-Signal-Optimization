export const DIRECTIONS = ["UP", "DOWN", "RIGHT", "LEFT"];
export const CLASSES = ["car", "motorbike", "bus", "truck"];
// Categorical colours (validated for dark surfaces, fixed order) and the two controller colours.
export const DIR_COLORS = { UP: "#3987e5", DOWN: "#d95926", RIGHT: "#199e70", LEFT: "#c98500" };
export const CLASS_COLORS = { car: "#3987e5", motorbike: "#d95926", bus: "#199e70", truck: "#c98500" };
export const CTRL_COLORS = { fixed: "#94a3b8", adaptive: "#22d3ee" };
export const num = (v, digits = 1) => (v == null || Number.isNaN(v) ? "-" : Number(v).toLocaleString(undefined, { maximumFractionDigits: digits }));
export const mmss = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
export const LEVEL_STYLE = { heavy: "bg-warn/15 text-warn", light: "bg-cyan/10 text-cyan", moderate: "bg-raised text-ink", insufficient: "bg-raised text-muted" };
