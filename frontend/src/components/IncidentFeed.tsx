import type { Incident } from '../types/watchdog';

interface Props {
  incidents: Incident[];
}

export default function IncidentFeed({ incidents }: Props) {
  return (
    <section className="bg-slate-900/70 border border-slate-800 rounded-xl p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300 mb-3">
        Agent Reasoning &amp; Guardrail Feed
      </h2>
      <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
        {incidents.map((inc) => (
          <div
            key={inc.id}
            className="bg-slate-950/90 border border-slate-800 rounded-lg p-4"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40">
                {inc.severity} • {inc.category.replace(/_/g, ' ')}
              </span>
              <span className="text-[10px] text-slate-500">
                {new Date(inc.timestamp).toLocaleTimeString()}
              </span>
            </div>

            <h3 className="text-sm font-bold text-white mt-2">{inc.title}</h3>

            {inc.prompt_injection_detected && (
              <div className="mt-2 p-2 rounded bg-purple-950/50 border border-purple-500/60 text-xs">
                <div className="font-bold text-purple-300">
                  🛡️ GUARDRAIL: Prompt Injection Blocked
                </div>
                {inc.sanitized_excerpt && (
                  <code className="block text-[11px] text-purple-200 mt-1 break-all">
                    {inc.sanitized_excerpt}
                  </code>
                )}
              </div>
            )}

            <p className="text-xs text-slate-300 mt-2 leading-relaxed">
              {inc.plain_english_explanation}
            </p>

            <div className="mt-3 pt-2 border-t border-slate-800 flex items-center justify-between text-[11px]">
              <span className="text-cyan-300 font-medium">
                Plan: {inc.proposed_action}
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
