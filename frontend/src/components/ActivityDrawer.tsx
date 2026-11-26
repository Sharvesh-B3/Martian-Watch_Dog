import { useState } from 'react';
import type { AuditEntry, Incident } from '../types/watchdog';
import SidePanel from './SidePanel';

interface Props {
  open: boolean;
  incidents: Incident[];
  audit: AuditEntry[];
  onClose: () => void;
}

function actorLabel(actor: AuditEntry['actor']): string {
  if (actor === 'AI_AGENT') return 'Agent';
  if (actor === 'HUMAN_OPERATOR') return 'Operator';
  if (actor === 'GUARDRAIL') return 'Guardrail';
  return 'System';
}

export default function ActivityDrawer({
  open,
  incidents,
  audit,
  onClose,
}: Props) {
  const [view, setView] = useState<'incidents' | 'audit'>('incidents');

  return (
    <SidePanel
      open={open}
      title="Activity"
      description="Recent incidents and the timestamped decision trail."
      onClose={onClose}
    >
      <div className="panel-tabs" role="tablist" aria-label="Activity view">
        <button
          type="button"
          role="tab"
          aria-selected={view === 'incidents'}
          onClick={() => setView('incidents')}
        >
          Incidents
          <span>{incidents.length}</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={view === 'audit'}
          onClick={() => setView('audit')}
        >
          Audit trail
          <span>{audit.length}</span>
        </button>
      </div>

      {view === 'incidents' ? (
        <div className="activity-list" role="tabpanel">
          {incidents.length === 0 && <p className="empty-copy">No incidents recorded.</p>}
          {incidents.slice(0, 30).map((incident) => (
            <article className="activity-entry" key={incident.id}>
              <div className="activity-entry__meta">
                <span className="severity-dot" data-severity={incident.severity} />
                <span>{incident.severity} severity</span>
                <time>{new Date(incident.timestamp).toLocaleTimeString()}</time>
              </div>
              <h3>{incident.title}</h3>
              <p>{incident.plain_english_explanation}</p>
              <span className="activity-entry__status">
                {incident.approval_status.replaceAll('_', ' ')}
              </span>
            </article>
          ))}
        </div>
      ) : (
        <div className="activity-list" role="tabpanel">
          {audit.length === 0 && <p className="empty-copy">No audit entries recorded.</p>}
          {audit.slice(0, 40).map((entry) => (
            <article className="activity-entry activity-entry--audit" key={entry.id}>
              <div className="activity-entry__meta">
                <span>{actorLabel(entry.actor)}</span>
                <time>{new Date(entry.timestamp).toLocaleTimeString()}</time>
              </div>
              <h3>{entry.action.replaceAll('_', ' ').toLowerCase()}</h3>
              <p>{entry.details}</p>
            </article>
          ))}
        </div>
      )}
    </SidePanel>
  );
}
