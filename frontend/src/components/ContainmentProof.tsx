import { Network, Route, ShieldCheck } from 'lucide-react';
import type { DeviceNode } from '../types/watchdog';

interface Props {
  decoy: DeviceNode;
}

function bytes(value: string | number | boolean | undefined): string {
  const amount = Number(value ?? 0);
  if (amount >= 1024 * 1024) return `${(amount / (1024 * 1024)).toFixed(1)} MB`;
  if (amount >= 1024) return `${(amount / 1024).toFixed(1)} KB`;
  return `${amount} B`;
}

export default function ContainmentProof({ decoy }: Props) {
  const metrics = decoy.metrics;
  return (
    <aside className="containment-proof" aria-labelledby="containment-proof-heading">
      <div className="containment-proof__icon" aria-hidden="true">
        <ShieldCheck size={23} />
      </div>
      <span className="section-kicker">Gateway confirmation</span>
      <h2 id="containment-proof-heading">Network reroute applied</h2>
      <p className="containment-proof__summary">
        The attacker reconnected through the same gateway and now terminates at the decoy broker.
      </p>

      <div className="route-proof" aria-label="Confirmed containment route">
        <span>Attacker</span>
        <Route aria-hidden="true" size={17} />
        <span>Gateway</span>
        <Route aria-hidden="true" size={17} />
        <strong>Decoy broker</strong>
      </div>

      <dl className="proof-metrics">
        <div>
          <dt>Gateway target</dt>
          <dd>{String(metrics.route_target ?? 'unknown')}</dd>
        </div>
        <div>
          <dt>Attacker reconnects</dt>
          <dd>{String(metrics.attacker_reconnects ?? 0)}</dd>
        </div>
        <div>
          <dt>Real-broker traffic</dt>
          <dd>{bytes(metrics.real_bytes)}</dd>
        </div>
        <div>
          <dt>Decoy traffic</dt>
          <dd>{bytes(metrics.decoy_bytes)}</dd>
        </div>
        <div>
          <dt>Payloads captured</dt>
          <dd>{String(metrics.captured_payloads ?? 0)}</dd>
        </div>
        <div>
          <dt>Active sessions</dt>
          <dd>{String(metrics.active_sessions ?? 0)}</dd>
        </div>
      </dl>

      <div className="proof-source">
        <Network aria-hidden="true" size={17} />
        <span>
          Last source <strong>{String(metrics.last_source ?? 'waiting')}</strong>
        </span>
      </div>
    </aside>
  );
}
