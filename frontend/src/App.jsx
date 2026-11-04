import { AnimatePresence, MotionConfig, motion } from "framer-motion";
import { BarChart3, Clock, History as HistoryIcon, LayoutDashboard, LineChart, Scale, SlidersHorizontal, TrafficCone } from "lucide-react";
import { useEffect, useState } from "react";
import { clearSession, getToken, getUsername, saveSession } from "./api/client.js";
import { Header, Sidebar } from "./components/Layout.jsx";
import { ToastProvider } from "./components/ui.jsx";
import { SettingsContext, useStoredSettings } from "./hooks/useSettings.js";
import Analytics from "./pages/Analytics.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import History from "./pages/History.jsx";
import Login from "./pages/Login.jsx";
import ModelComparison from "./pages/ModelComparison.jsx";
import Optimization from "./pages/Optimization.jsx";
import PeakHour from "./pages/PeakHour.jsx";
import Prediction from "./pages/Prediction.jsx";
import Simulation from "./pages/Simulation.jsx";

const PAGES = [
  { id: "dashboard", title: "Dashboard", heading: "Traffic Intelligence Dashboard", icon: LayoutDashboard, Page: Dashboard,
    subtitle: "Pune junction video counts, ML demand prediction and Fixed-Time vs Adaptive signal simulation. Data: 100,000 selected records of the Pune (Jan 2023) dataset." },
  { id: "prediction", title: "Traffic Prediction", heading: "Traffic Prediction", icon: LineChart, Page: Prediction, subtitle: "XGBoost forecast of the vehicles arriving in the next few seconds, checked on clips the model never saw." },
  { id: "peak", title: "Peak-Hour Analysis", heading: "Peak-Hour Analysis", icon: Clock, Page: PeakHour, subtitle: "Busiest observed periods, discovered from the data rather than assumed." },
  { id: "optimization", title: "Signal Optimization", heading: "Signal Optimization", icon: SlidersHorizontal, Page: Optimization, subtitle: "A Genetic Algorithm allocates green time to the four modelled phases. Recommendations only, no real signals are controlled." },
  { id: "simulation", title: "Live Simulation", heading: "Live Simulation", icon: TrafficCone, Page: Simulation, subtitle: "Step-by-step queue simulation driven by the backend. It is simulated traffic, not live road data." },
  { id: "analytics", title: "Waiting-Time Analytics", heading: "Waiting-Time & Queue Analytics", icon: BarChart3, Page: Analytics, subtitle: "Fixed-Time vs Adaptive results from completed simulation runs on identical arrivals." },
  { id: "models", title: "Model Comparison", heading: "Model Comparison", icon: Scale, Page: ModelComparison, subtitle: "Test-set results for XGBoost, Linear Regression, Random Forest and two simple baselines." },
  { id: "history", title: "Experiment History", heading: "Experiment History", icon: HistoryIcon, Page: History, subtitle: "Saved experiments from the database: review details and compare runs." },
];

function Shell({ username, onLogout }) {
  const [current, setCurrent] = useState(() => (PAGES.some((p) => p.id === location.hash.slice(1)) ? location.hash.slice(1) : "dashboard"));
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsedState] = useState(() => localStorage.getItem("traffic_ai_collapsed") === "1");
  const setCollapsed = (v) => { setCollapsedState(v); try { localStorage.setItem("traffic_ai_collapsed", v ? "1" : "0"); } catch { /* ignore */ } };
  useEffect(() => { location.hash = current; document.title = `${PAGES.find((p) => p.id === current).title} | Traffic-AI`; }, [current]);
  const { heading, subtitle, Page } = PAGES.find((p) => p.id === current);
  return (
    <div className="flex min-h-screen">
      <Sidebar pages={PAGES} current={current} onSelect={setCurrent} username={username} onLogout={onLogout} collapsed={collapsed} setCollapsed={setCollapsed} open={open} setOpen={setOpen} />
      <main className="min-w-0 flex-1 px-4 py-6 sm:px-8">
        <Header title={heading} subtitle={subtitle} onMenu={() => setOpen(true)} />
        <AnimatePresence mode="wait">
          <motion.div key={current} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
            <Page goTo={setCurrent} />
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}

export default function App() {
  const [username, setUsername] = useState(() => (getToken() ? getUsername() : null));
  const settingsState = useStoredSettings();
  useEffect(() => {  // the API client fires this when a token is rejected or expires
    const signedOut = () => setUsername(null);
    window.addEventListener("auth:logout", signedOut);
    return () => window.removeEventListener("auth:logout", signedOut);
  }, []);
  const logout = () => { clearSession(); setUsername(null); };
  return (
    <MotionConfig reducedMotion="user">
      <ToastProvider>
        <SettingsContext.Provider value={settingsState}>
          {username ? <Shell username={username} onLogout={logout} /> : <Login onLogin={(token, name) => { saveSession(token, name); setUsername(name); }} />}
        </SettingsContext.Provider>
      </ToastProvider>
    </MotionConfig>
  );
}
