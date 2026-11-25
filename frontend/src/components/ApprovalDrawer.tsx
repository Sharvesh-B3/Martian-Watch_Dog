import type { ApprovalRequest } from '../types/watchdog';

interface Props {
  approvals: ApprovalRequest[];
  onDecision: (approval: ApprovalRequest, decision: 'approved' | 'rejected') => void;
}

export default function ApprovalDrawer({ approvals, onDecision }: Props) {
  return (
    <section className="bg-slate-900/70 border border-amber-500/40 rounded-xl p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-amber-300 mb-3">
        Human-in-the-Loop Action Gate ({approvals.length} Pending)
      </h2>

      {approvals.length === 0 ? (
        <p className="text-xs text-slate-400">
          No high-risk containment actions awaiting operator sign-off.
        </p>
      ) : (
        <div className="space-y-3">
          {approvals.map((apr) => (
            <div
              key={apr.id}
              className="bg-amber-950/20 border border-amber-500/50 rounded-lg p-4"
            >
              <div className="text-xs font-bold text-amber-300 uppercase">
                Target: {apr.target_device_id}
              </div>
              <div className="text-sm font-semibold text-white mt-1">
                {apr.recommended_action}
              </div>
              <p className="text-xs text-slate-300 mt-1">{apr.risk_summary}</p>
              <div className="flex gap-2 mt-4">
                <button
                  type="button"
                  onClick={() => onDecision(apr, 'approved')}
                  className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold py-2 rounded transition"
                >
                  ✓ Approve Containment
                </button>
                <button
                  type="button"
                  onClick={() => onDecision(apr, 'rejected')}
                  className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold py-2 rounded transition"
                >
                  ✕ Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
