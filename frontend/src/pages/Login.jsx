import { motion } from "framer-motion";
import { BrainCircuit, Dna, Eye, EyeOff, Loader2, LogIn, TrafficCone, UserPlus } from "lucide-react";
import { useEffect, useState } from "react";
import { api, errorMessage } from "../api/client.js";
import { ErrorBox, Field, inputClass } from "../components/ui.jsx";

const FEATURES = [
  [BrainCircuit, "XGBoost demand prediction", "Forecasts vehicle arrivals from Pune junction video counts"],
  [Dna, "Genetic Algorithm timing", "Allocates green time to the four modelled phases"],
  [TrafficCone, "Fixed-Time vs Adaptive", "Simulated queues and waiting times on identical arrivals"],
];

const LAMPS = [["#ef4444", "red"], ["#facc15", "yellow"], ["#22c55e", "green"]];

/** Traffic light that keeps cycling red -> yellow -> green. `row` = small horizontal version for phones. */
function TrafficLight({ row = false }) {
  const [active, setActive] = useState(0);
  useEffect(() => { const timer = setInterval(() => setActive((n) => (n + 1) % 3), 1600); return () => clearInterval(timer); }, []);
  return (
    <div role="img" aria-label={`Traffic light showing ${LAMPS[active][1]}`} className={`inline-flex gap-3 rounded-2xl border border-line bg-page shadow-lg ${row ? "p-2.5" : "flex-col p-4"}`}>
      {LAMPS.map(([color], i) => <span key={color} className={`rounded-full transition-all duration-500 ${row ? "h-6 w-6" : "h-14 w-14"}`}
        style={{ backgroundColor: active === i ? color : "#1c2740", boxShadow: active === i ? `0 0 26px ${color}99` : "none" }} />)}
    </div>
  );
}

export default function Login({ onLogin }) {
  const [registering, setRegistering] = useState(false);
  const [form, setForm] = useState({ username: "", password: "", confirm: "" });
  const [show, setShow] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    if (registering && form.password !== form.confirm) return setError("The two passwords do not match.");
    setBusy(true);
    try {
      const { token, username } = await (registering ? api.register : api.login)({ username: form.username, password: form.password });
      onLogin(token, username);
    } catch (err) { setError(errorMessage(err)); } finally { setBusy(false); }
  };
  return (
    <div className="flex min-h-screen">
      <div className="hidden w-1/2 flex-col justify-between border-r border-line bg-panel p-12 lg:flex">
        <div className="flex items-center gap-3"><span className="flex h-11 w-11 items-center justify-center rounded-xl bg-cyan/15 text-cyan"><TrafficCone size={24} /></span>
          <div><div className="text-xl font-bold">Traffic-AI</div><div className="text-sm text-muted">AI-based adaptive traffic signal optimization</div></div></div>
        <div className="space-y-6">
          <TrafficLight />
          <h1 className="max-w-md text-4xl font-bold leading-tight tracking-tight">Shorter queues start with better green times.</h1>
          <ul className="space-y-4">{FEATURES.map(([Icon, title, text]) => (
            <li key={title} className="flex items-start gap-3"><span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-raised text-cyan"><Icon size={18} /></span>
              <span><span className="block font-semibold">{title}</span><span className="text-sm text-muted">{text}</span></span></li>))}</ul>
        </div>
        <p className="text-xs text-muted">MCA final-year project prototype. Results are simulated estimates from a small Pune video-count dataset; no real signals are controlled.</p>
      </div>
      <div className="flex flex-1 items-center justify-center px-6 py-10">
        <motion.form onSubmit={submit} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-sm space-y-4">
          <div className="lg:hidden"><TrafficLight row /></div>
          <div><h2 className="text-3xl font-bold">{registering ? "Create account" : "Sign in"}</h2>
            <p className="mt-1 text-sm text-muted">{registering ? "Choose a username and password." : "Open the Traffic Intelligence Dashboard."}</p></div>
          <Field label="Username"><input className={inputClass} value={form.username} onChange={set("username")} autoComplete="username" autoFocus required /></Field>
          <Field label="Password">
            <div className="relative">
              <input className={`${inputClass} pr-10`} type={show ? "text" : "password"} value={form.password} onChange={set("password")} autoComplete={registering ? "new-password" : "current-password"} required />
              <button type="button" onClick={() => setShow(!show)} aria-label={show ? "Hide password" : "Show password"} className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-muted hover:text-ink">{show ? <EyeOff size={17} /> : <Eye size={17} />}</button>
            </div>
          </Field>
          {registering && <Field label="Confirm password"><input className={inputClass} type={show ? "text" : "password"} value={form.confirm} onChange={set("confirm")} autoComplete="new-password" required /></Field>}
          {error && <ErrorBox message={error} />}
          <button type="submit" disabled={busy} className="flex w-full items-center justify-center gap-2 rounded-lg bg-cyan py-2.5 font-semibold text-page transition hover:bg-cyan-300 disabled:opacity-60">
            {busy ? <Loader2 size={18} className="animate-spin" /> : registering ? <UserPlus size={18} /> : <LogIn size={18} />}{busy ? "Please wait..." : registering ? "Create account" : "Sign in"}
          </button>
          <p className="text-center text-sm text-muted">{registering ? "Already registered?" : "First time here?"}{" "}
            <button type="button" onClick={() => { setRegistering(!registering); setError(null); }} className="font-semibold text-cyan hover:underline">{registering ? "Sign in" : "Create an account"}</button></p>
          <p className="text-center text-xs text-muted">Username: 3-30 letters, numbers, dot, dash or underscore. Password: at least 6 characters.</p>
        </motion.form>
      </div>
    </div>
  );
}
