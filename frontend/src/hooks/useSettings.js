import { createContext, useContext, useState } from "react";

/** Signal-timing ASSUMPTIONS shared by the optimisation, simulation and analytics pages (kept in this browser only). */
export const DEFAULT_SETTINGS = { cycle_length: 120, min_green: 10, max_green: 60, lost_time: 4, saturation_flow: 3600, fixed_plan: "equal" };
export const SettingsContext = createContext({ settings: DEFAULT_SETTINGS, setSettings: () => {} });
export const useSettings = () => useContext(SettingsContext);

export function useStoredSettings() {
  const [settings, set] = useState(() => {
    try { return { ...DEFAULT_SETTINGS, ...JSON.parse(localStorage.getItem("traffic_ai_settings") || "{}") }; } catch { return DEFAULT_SETTINGS; }
  });
  const setSettings = (next) => {
    set(next);
    try { localStorage.setItem("traffic_ai_settings", JSON.stringify(next)); } catch { /* private mode: keep in memory only */ }
  };
  return { settings, setSettings };
}
