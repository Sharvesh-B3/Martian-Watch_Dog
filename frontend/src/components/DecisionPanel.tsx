import { Check, ShieldAlert, X } from 'lucide-react';
import type { ApprovalDecision } from '../api/client';
import type { ApprovalRequest, DeviceNode } from '../types/watchdog';

interface Props {
  approval: ApprovalRequest;
  devices: DeviceNode[];
  pending: boolean;
  onDecision: (
    approval: ApprovalRequest,
    decision: ApprovalDecision
  ) => Promise<void>;
}

export default function DecisionPanel({
  approval,
  devices,
  pending,
  onDecision,
}: Props) {
  const target = devices.find((device) => device.id === approval.target_device_id);

  const decide = (decision: ApprovalDecision) => {
    void onDecision(approval, decision).catch(() => undefined);
  };

  return (
    <aside className="decision-panel" aria-labelledby="decision-heading" aria-busy={pending}>
      <div className="decision-panel__icon" aria-hidden="true">
        <ShieldAlert size={23} />
      </div>
      <span className="section-kicker">Human approval required</span>
      <h2 id="decision-heading">Review containment</h2>

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
      </div>
    </aside>
  );
}
