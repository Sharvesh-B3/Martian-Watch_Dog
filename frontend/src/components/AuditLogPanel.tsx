import type { AuditEntry } from '../types/watchdog';

interface Props {
  entries: AuditEntry[];
}

export default function AuditLogPanel({ entries }: Props) {
  return (
    <section className="bg-slate-900/70 border border-slate-800 rounded-xl p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300 mb-3">
        Immutable Decision &amp; Action Audit Log
      </h2>
      <div className="space-y-2 max-h-60 overflow-y-auto pr-1 font-mono text-xs">
        {entries.map((entry) => (
          <div
            key={entry.id}
            className="flex items-start justify-between gap-3 bg-slate-950/80 border border-slate-800/80 rounded p-2.5"
          >
            <div>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-cyan-300 mr-2">
                {entry.actor}
              </span>
              <span className="text-slate-200 font-semibold">{entry.action}</span>
              <p className="text-slate-400 mt-1">{entry.details}</p>
            </div>
            <span className="text-[10px] text-slate-500 shrink-0">
              {new Date(entry.timestamp).toLocaleTimeString()}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
