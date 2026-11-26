import { ArrowRight, ShieldCheck, TriangleAlert } from 'lucide-react';
import type { DeviceNode, Incident } from '../types/watchdog';
import CorrelationMap from './CorrelationMap';
import { DEVICE_VISUALS } from './deviceVisuals';

interface Props {
  incident: Incident | null;
  devices: DeviceNode[];
  selectedDeviceId: string | null;
  onSelectDevice: (deviceId: string) => void;
}

function incidentState(incident: Incident): string {
  if (incident.approval_status === 'pending') return 'Awaiting operator decision';
  if (incident.approval_status === 'approved') return 'Containment approved';
  if (incident.approval_status === 'rejected') return 'Action rejected';
  return 'Automatic action applied';
}

export default function ThreatWorkspace({
  incident,
  devices,
  selectedDeviceId,
  onSelectDevice,
}: Props) {
  const correlatedIds = incident?.correlated_device_ids ?? [];
  const names = correlatedIds.map((id) => {
    const device = devices.find((item) => item.id === id);
    return device?.name ?? id;
  });

  return (
    <section className="threat-workspace" aria-labelledby="threat-heading">
      <div className="threat-head">
        <div className="threat-head__copy">
          <span className="section-kicker">
            {incident ? incidentState(incident) : 'Live protection'}
          </span>
          <h1 id="threat-heading">
            {incident?.title ?? 'No active incident'}
          </h1>
          <p>
            {incident?.plain_english_explanation ??
              'Five synthetic devices are reporting. The 60-second correlation window has no threat to review.'}
          </p>
        </div>
        {incident ? (
          <span className="severity-label" data-severity={incident.severity}>
            <TriangleAlert aria-hidden="true" size={16} />
            {incident.severity} severity
          </span>
        ) : (
          <span className="severity-label" data-severity="clear">
            <ShieldCheck aria-hidden="true" size={16} />
            Monitoring
          </span>
        )}
      </div>

      <CorrelationMap
        devices={devices}
        correlatedIds={correlatedIds}
        selectedId={selectedDeviceId}
        onSelect={onSelectDevice}
      />

      {incident && (
        <div className="incident-evidence">
          <div className="evidence-block">
            <span>Evidence</span>
            <div className="evidence-devices">
              {names.map((name, index) => {
                const device = devices.find(
                  (item) => item.id === correlatedIds[index]
                );
                const visual = device ? DEVICE_VISUALS[device.type] : null;
                const Icon = visual?.icon;
                return (
                  <button
                    type="button"
                    key={correlatedIds[index]}
                    onClick={() => onSelectDevice(correlatedIds[index])}
                  >
                    {Icon && <Icon aria-hidden="true" size={16} />}
                    {name}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="evidence-block evidence-block--action">
            <span>Proposed action</span>
            <p>
              {incident.proposed_action}
              <ArrowRight aria-hidden="true" size={16} />
            </p>
          </div>
        </div>
      )}

      {incident?.prompt_injection_detected && incident.sanitized_excerpt && (
        <div className="guardrail-evidence" role="status">
          <div>
            <ShieldCheck aria-hidden="true" size={18} />
            <strong>Blocked input</strong>
          </div>
          <code>{incident.sanitized_excerpt}</code>
        </div>
      )}
    </section>
  );
}
