import { motion } from "framer-motion";
import { LogOut, Menu, PanelLeftClose, PanelLeftOpen, TrafficCone, UserCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api/client.js";

export function Sidebar({ pages, current, onSelect, username, onLogout, collapsed, setCollapsed, open, setOpen }) {
  const pick = (id) => { onSelect(id); setOpen(false); };
  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-black/60 md:hidden" onClick={() => setOpen(false)} />}
      <aside aria-label="Main navigation" className={`fixed inset-y-0 left-0 z-40 flex w-64 shrink-0 flex-col border-r border-line bg-panel px-3 py-4 transition-transform md:sticky md:top-0 md:h-screen md:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"} ${collapsed ? "md:w-[76px]" : "md:w-64"}`}>
        <div className={`mb-4 flex items-center gap-3 border-b border-line px-1 pb-4 ${collapsed ? "md:justify-center" : ""}`}>
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-cyan/15 text-cyan"><TrafficCone size={22} /></span>
          <div className={collapsed ? "md:hidden" : ""}><div className="font-bold leading-tight">Traffic-AI</div><div className="text-xs text-muted">Adaptive signal optimization</div></div>
        </div>
        <nav className="flex flex-col gap-1 overflow-y-auto">
          {pages.map(({ id, title, icon: Icon }) => (
            <button key={id} onClick={() => pick(id)} title={title} aria-current={current === id ? "page" : undefined}
                    className={`relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition ${collapsed ? "md:justify-center" : ""} ${current === id ? "bg-cyan/10 font-semibold text-cyan" : "text-muted hover:bg-raised hover:text-ink"}`}>
              {current === id && <motion.span layoutId="active-nav" className="absolute inset-y-1.5 left-0 w-[3px] rounded-full bg-cyan" />}
              <Icon size={18} className="shrink-0" /><span className={collapsed ? "md:hidden" : ""}>{title}</span>
            </button>
          ))}
        </nav>
        <div className="mt-auto space-y-2 border-t border-line pt-3">
          <button onClick={() => setCollapsed(!collapsed)} className="hidden w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted hover:bg-raised hover:text-ink md:flex" aria-label="Collapse or expand sidebar">
            {collapsed ? <PanelLeftOpen size={18} /> : <><PanelLeftClose size={18} /> Collapse</>}
          </button>
          <div className={`flex items-center justify-between rounded-lg bg-raised px-3 py-2 text-sm ${collapsed ? "md:justify-center" : ""}`}>
            <span className="flex min-w-0 items-center gap-2"><UserCircle size={18} className="shrink-0 text-cyan" /><span className={`truncate ${collapsed ? "md:hidden" : ""}`}>{username}</span></span>
            <button onClick={onLogout} title="Sign out" aria-label="Sign out" className={`rounded p-1 text-muted hover:text-ink ${collapsed ? "md:hidden" : ""}`}><LogOut size={16} /></button>
          </div>
        </div>
      </aside>
    </>
  );
}

/** API connection: green = connected, red = disconnected, amber = connected but the dataset or model is missing. */
function StatusBadge() {
  const [status, setStatus] = useState({ state: "checking", label: "Checking API..." });
  useEffect(() => {
    const check = () => api.health().then((h) => setStatus(h.dataset_available && h.model_available
      ? { state: "ok", label: "API connected" } : { state: "warn", label: "API connected - setup needed", hint: h.detail.join(" ") }))
      .catch(() => setStatus({ state: "off", label: "API disconnected" }));
    check();
    const timer = setInterval(check, 5000);
    return () => clearInterval(timer);
  }, []);
  const style = { ok: "border-good/40 text-good", warn: "border-warn/50 text-warn", off: "border-bad/60 text-bad", checking: "border-line text-muted" }[status.state];
  const dot = { ok: "bg-good", warn: "bg-warn", off: "bg-bad", checking: "bg-muted" }[status.state];
  return <span title={status.hint} role="status" className={`inline-flex max-w-[16rem] items-center gap-2 rounded-full border bg-panel px-3 py-1.5 text-xs font-medium ${style}`}><i className={`h-2 w-2 shrink-0 rounded-full ${dot}`} /> <span className="truncate">{status.label}</span></span>;
}

export function Header({ title, subtitle, onMenu }) {
  return (
    <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div className="flex min-w-0 items-start gap-3">
        <button onClick={onMenu} aria-label="Open menu" className="mt-1 rounded-lg border border-line p-2 text-muted hover:text-ink md:hidden"><Menu size={18} /></button>
        <div className="min-w-0"><h1 className="text-2xl font-bold tracking-tight">{title}</h1><p className="mt-1 max-w-3xl text-sm text-muted">{subtitle}</p></div>
      </div>
      <StatusBadge />
    </header>
  );
}
