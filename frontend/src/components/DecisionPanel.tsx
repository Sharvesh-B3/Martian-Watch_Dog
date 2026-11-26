import { Check, RotateCcw, ShieldAlert, X } from 'lucide-react';
import type { ApprovalDecision } from '../api/client';
import type { ApprovalRequest, DeviceNode } from '../types/watchdog';

interface Props {
  approval: ApprovalRequest;
  devices: DeviceNode[];
  pending: boolean;
  replayPending?: boolean;
  canReplay?: boolean;
  onDecision: (
    approval: ApprovalRequest,
    decision: ApprovalDecision
  ) => Promise<void>;
  onReplay?: () => Promise<void>;
}

export default function DecisionPanel({
  approval,
  devices,
  pending,
  replayPending = false,
  canReplay = true,
  onDecision,
  onReplay,
}: Props) {
  const target = devices.find((device) => device.id === approval.target_device_id);

  const decide = (decision: ApprovalDecision) => {
    void onDecision(approval, decision).catch(() => undefined);
  };

  const replay = () => {
    void onReplay?.().catch(() => undefined);
  };

  const isPending = approval.status === 'pending';

  return (
    <aside className="decision-panel" aria-labelledby="decision-heading" aria-busy={pending}>
      <div className="decision-panel__icon" aria-hidden="true">
        <ShieldAlert size={23} />
      </div>
      <span className="section-kicker">
        {isPending ? 'Human approval required' : 'Last human decision'}
      </span>
      <h2 id="decision-heading">
        {isPending
          ? 'Review containment'
          : approval.status === 'approved'
            ? 'Containment approved'
            : 'Containment rejected'}
      </h2>
      {!isPending && (
        <span className="decision-status" data-status={approval.status}>
          {approval.status}
        </span>
      )}

      <dl className="decision-facts">
        <div>
          <dt>Target</dt>
          <dd>{target?.name ?? approval.target_device_id}</dd>
        </div>
        <div>
          <dt>Action</dt>
          <dd>{approval.recommended_action}</dd>
        </div>
      </dl>

      <div className="risk-summary">
        <span>Operational impact</span>
        <p>{approval.risk_summary}</p>
      </div>

      <div className="decision-actions">
        {isPending ? (
          <>
            <button
              className="button button--primary button--wide"
              type="button"
              disabled={pending}
              onClick={() => decide('approved')}
            >
              <Check aria-hidden="true" size={18} />
              {pending ? 'Recording decision' : 'Approve containment'}
            </button>
            <button
              className="button button--secondary button--wide"
              type="button"
              disabled={pending}
              onClick={() => decide('rejected')}
            >
              <X aria-hidden="true" size={18} />
              Reject action
            </button>
          </>
        ) : (
          onReplay && (
            <button
              className="button button--secondary button--wide"
              type="button"
              disabled={replayPending || !canReplay}
              title={
                canReplay
                  ? undefined
                  : 'Activate the agent to replay a high-risk scenario'
              }
              onClick={replay}
            >
              <RotateCcw aria-hidden="true" size={18} />
              {replayPending
                ? 'Starting scenario'
                : canReplay
                  ? 'Run scenario again'
                  : 'Activate agent to replay'}
            </button>
          )
        )}
      </div>
    </aside>
  );
}
