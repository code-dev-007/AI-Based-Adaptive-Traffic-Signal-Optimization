import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Inbox, Loader2, XCircle } from "lucide-react";
import { createContext, useCallback, useContext, useState } from "react";

// Every number on screen carries one of these labels, so observed data, ML output, simulation and assumptions are never mixed up.
const TAGS = {
  observed: ["Observed Data", "bg-sky-400/10 text-sky-300"], estimated: ["Estimated Rate", "bg-amber-400/10 text-amber-300"],
  aggregated: ["Aggregated Across Selected Dates", "bg-slate-500/20 text-slate-300"], predicted: ["ML prediction", "bg-cyan/10 text-cyan"],
  simulated: ["Simulated estimate", "bg-violet-400/10 text-violet-300"], assumption: ["Assumption", "bg-slate-500/20 text-slate-300"],
  hypothetical: ["Hypothetical what-if", "bg-warn/15 text-warn"],
};
const TONES = { cyan: "text-cyan bg-cyan/10", good: "text-good bg-good/10", warn: "text-warn bg-warn/10", bad: "text-bad bg-bad/10", blue: "text-blue-400 bg-blue-400/10" };
export const inputClass = "mt-1 w-full rounded-lg border border-line bg-raised px-3 py-2 text-sm text-ink placeholder:text-muted focus:border-cyan focus:outline-none";

export const Tag = ({ kind }) => <span className={`inline-block rounded-md px-2 py-0.5 text-[11px] font-semibold ${TAGS[kind][1]}`}>{TAGS[kind][0]}</span>;

export function Card({ title, subtitle, tag, actions, children, className = "" }) {
  return (
    <section className={`rounded-xl border border-line bg-panel p-5 shadow-lg shadow-black/20 ${className}`}>
      {(title || tag || actions) && (
        <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
          <div><h2 className="text-base font-semibold">{title}</h2>{subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}</div>
          <div className="flex items-center gap-2">{tag && <Tag kind={tag} />}{actions}</div>
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, unit, sub, icon: Icon, tone = "cyan", tag, loading }) {
  return (
    <div className="rounded-xl border border-line bg-panel p-4 shadow-lg shadow-black/20">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-muted">{label}</span>
        <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${TONES[tone]}`}><Icon size={17} /></span>
      </div>
      {loading ? <Skeleton className="mt-3 h-8 w-28" /> : <div className="mt-1 text-2xl font-bold tracking-tight">{value}<span className="ml-1 text-sm font-medium text-muted">{unit}</span></div>}
      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">{tag && <Tag kind={tag} />}<span>{sub}</span></div>
    </div>
  );
}

export const Skeleton = ({ className = "h-6 w-full" }) => <div className={`animate-pulse rounded-md bg-raised ${className}`} />;
export const Note = ({ children, tone = "info" }) => (
  <p className={`my-3 rounded-lg border px-4 py-3 text-sm ${tone === "warn" ? "border-warn/40 bg-warn/10 text-amber-100" : "border-cyan/30 bg-cyan/5 text-cyan-50"}`}>{children}</p>
);
export const ErrorBox = ({ message }) => (
  <div role="alert" className="flex items-start gap-3 rounded-lg border border-bad/40 bg-bad/10 px-4 py-3 text-sm text-red-100"><AlertTriangle size={18} className="mt-0.5 shrink-0 text-bad" /> <span>{message}</span></div>
);
export const Empty = ({ title, text, icon: Icon = Inbox, children }) => (
  <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-line px-6 py-10 text-center">
    <Icon size={28} className="text-muted" /><p className="font-semibold">{title}</p><p className="max-w-md text-sm text-muted">{text}</p>{children}
  </div>
);
export const Loading = () => <div className="grid gap-3"><Skeleton className="h-24" /><Skeleton className="h-48" /></div>;

/** Tooltip for a technical term (works with hover and keyboard focus). */
export const Tip = ({ text, children }) => (
  <span className="group relative cursor-help border-b border-dotted border-muted" tabIndex={0}>
    {children}
    <span role="tooltip" className="pointer-events-none absolute left-0 top-full z-30 mt-1 hidden w-64 rounded-lg border border-line bg-raised p-2 text-xs font-normal text-ink shadow-xl group-hover:block group-focus:block">{text}</span>
  </span>
);

export const Field = ({ label, hint, children }) => <label className="block text-sm font-medium"><span>{label}</span>{children}{hint && <span className="mt-1 block text-xs font-normal text-muted">{hint}</span>}</label>;
export const Select = ({ label, options, ...props }) => (
  <Field label={label}><select className={inputClass} {...props}>{options.map((o) => <option key={o.value ?? o} value={o.value ?? o}>{o.label ?? o}</option>)}</select></Field>
);
export const NumberInput = ({ label, hint, min, max, step = 1, value, onChange }) => {
  const bad = value === "" || value < min || value > max;
  return (
    <Field label={label} hint={bad ? `Enter a value from ${min} to ${max}.` : hint}>
      <input type="number" className={`${inputClass} ${bad ? "border-bad" : ""}`} min={min} max={max} step={step} value={value} aria-invalid={bad}
             onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))} />
    </Field>
  );
};

export function Button({ children, variant = "secondary", icon: Icon, busy, ...props }) {
  const style = variant === "primary" ? "bg-cyan text-page hover:bg-cyan-300" : variant === "danger" ? "bg-bad/90 text-white hover:bg-bad" : "border border-line bg-raised text-ink hover:border-cyan hover:text-cyan";
  return (
    <button {...props} disabled={busy || props.disabled} className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 ${style}`}>
      {busy ? <Loader2 size={16} className="animate-spin" /> : Icon && <Icon size={16} />}{children}
    </button>
  );
}

/** Generic table: cols = [{ h: header, f: row => cell, right?: true }]. */
export const Table = ({ cols, rows, onRow }) => (
  <div className="overflow-x-auto">
    <table className="w-full text-left text-sm">
      <thead><tr className="border-b border-line text-muted">{cols.map((c) => <th key={c.h} scope="col" className={`whitespace-nowrap px-3 py-2 font-medium ${c.right ? "text-right" : ""}`}>{c.h}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => (
        <tr key={r.id ?? i} className="border-b border-line/60 hover:bg-raised/50" onClick={onRow && (() => onRow(r))}>
          {cols.map((c) => <td key={c.h} className={`px-3 py-2 ${c.right ? "text-right tabular-nums" : ""}`}>{c.f(r)}</td>)}
        </tr>))}</tbody>
    </table>
  </div>
);

/** Shows a skeleton / error box while a useApi result is not ready; otherwise renders children(data). */
export function Async({ state, children }) {
  if (state.loading && !state.data) return <Loading />;
  if (state.error) return <ErrorBox message={state.error} />;
  return children(state.data);
}

const ToastContext = createContext(() => {});
export const useToast = () => useContext(ToastContext);
export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const push = useCallback((text, type = "ok") => {
    const id = Math.random();
    setItems((list) => [...list, { id, text, type }]);
    setTimeout(() => setItems((list) => list.filter((i) => i.id !== id)), 4500);
  }, []);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div role="status" aria-live="polite" className="fixed bottom-4 right-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2">
        <AnimatePresence>{items.map((t) => (
          <motion.div key={t.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                      className={`flex items-start gap-2 rounded-lg border bg-raised px-3 py-2 text-sm shadow-xl ${t.type === "error" ? "border-bad/60" : "border-good/50"}`}>
            {t.type === "error" ? <XCircle size={17} className="mt-0.5 shrink-0 text-bad" /> : <CheckCircle2 size={17} className="mt-0.5 shrink-0 text-good" />}<span>{t.text}</span>
          </motion.div>))}</AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}
