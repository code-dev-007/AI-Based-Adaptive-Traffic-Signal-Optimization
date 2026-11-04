export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {  // dark navy theme: page < panel < raised; cyan = AI / primary, green = success, amber = peak / warning, red = critical
        page: "#0a1020", panel: "#101a30", raised: "#16223d", line: "#22304f", ink: "#e6edf7", muted: "#8d9bb8",
        cyan: { DEFAULT: "#22d3ee", dim: "#0e7490" }, good: "#22c55e", warn: "#f59e0b", bad: "#ef4444",
      },
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
};
