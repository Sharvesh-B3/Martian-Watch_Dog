import { useEffect, useState } from 'react';
import ApprovalDrawer from '../components/ApprovalDrawer';
import AuditLogPanel from '../components/AuditLogPanel';
import IncidentFeed from '../components/IncidentFeed';
import WingFloorplan from '../components/WingFloorplan';
import {
  USE_MOCK_DATA,
  decideApproval,
  fetchDashboardState,
  setAgentMode,
  subscribeToStream,
  triggerSimAttack,
  type ApprovalDecision,
  type AttackType,
  type StreamEvent,
} from '../api/client';
import type {
  ApprovalRequest,
  AuditEntry,
  DeviceNode,
  Incident,
} from '../types/watchdog';

function upsertById<T extends { id: string }>(list: T[], item: T): T[] {
  const index = list.findIndex((entry) => entry.id === item.id);
  if (index === -1) return [item, ...list];
  const next = [...list];
  next[index] = item;
  return next;
}

export default function CommandCenter() {
  const [devices, setDevices] = useState<DeviceNode[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [agentEnabled, setAgentEnabled] = useState(true);
  const [agentModePending, setAgentModePending] = useState(false);
  const [controlError, setControlError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    fetchDashboardState().then((data) => {
      if (!active) return;
      setDevices(data.devices);
      setIncidents(data.incidents);
      setApprovals(data.approvals);
      setAudit(data.audit);
    });

    const handleEvent = (event: StreamEvent) => {
      switch (event.type) {
        case 'device_update':
          setDevices((prev) => upsertById(prev, event.device));
          break;
        case 'new_incident':
          setIncidents((prev) => upsertById(prev, event.incident));
          break;
        case 'new_approval':
          setApprovals((prev) => upsertById(prev, event.approval));
          break;
        case 'audit_entry':
          setAudit((prev) => upsertById(prev, event.entry));
          break;
      }
    };

    const unsubscribe = subscribeToStream(handleEvent);
    return () => {
      active = false;
      unsubscribe();
    };
  }, []);

  const toggleAgent = async () => {
    const next = !agentEnabled;
    setAgentModePending(true);
    setControlError(null);
    try {
      const response = await setAgentMode(next);
      setAgentEnabled(response.enabled);
    } catch (error: unknown) {
      console.error('Agent mode update failed', error);
      setControlError('Could not update Agent mode. Check the backend connection.');
    } finally {
      setAgentModePending(false);
    }
  };

  const handleDecision = (
    approval: ApprovalRequest,
    decision: ApprovalDecision
  ) => {
    setControlError(null);
    void decideApproval(approval.id, decision).catch((error: unknown) => {
      console.error('Approval decision failed', error);
      setControlError('Approval decision failed. Check the backend connection.');
    });
  };

  const handleTriggerAttack = (attackType: AttackType) => {
    setControlError(null);
    void triggerSimAttack(attackType).catch((error: unknown) => {
      console.error('Attack trigger failed', error);
      setControlError(
        'Attack trigger failed. Verify the backend and Gemini are available.'
      );
    });
  };

  const pendingApprovals = approvals.filter((a) => a.status === 'pending');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 font-sans">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4 mb-6">
        <div>
          <div className="flex items-center gap-3">
            <span className="h-3 w-3 rounded-full bg-emerald-400 animate-ping" />
            <h1 className="text-2xl font-bold tracking-tight">
              AEGIS WATCHDOG // Campus IoT SOC
            </h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Isolated Docker MQTT Lab • Sense → Think → Act → Explain • HITL
            Enforced • {USE_MOCK_DATA ? 'MOCK LAB' : 'LIVE BACKEND'}
          </p>
          {controlError && (
            <p className="text-xs text-rose-300 mt-1" role="alert">
              {controlError}
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => void toggleAgent()}
            disabled={agentModePending}
            className={`px-3 py-1.5 rounded text-xs font-semibold border transition ${
              agentEnabled
                ? 'bg-emerald-600/20 border-emerald-500 text-emerald-300'
                : 'bg-rose-600/20 border-rose-500 text-rose-300'
            } disabled:cursor-wait disabled:opacity-60`}
          >
            {agentModePending
              ? '◌ UPDATING AGENT MODE...'
              : agentEnabled
              ? '● WATCHDOG AGENT: ACTIVE'
              : '○ WATCHDOG AGENT: BYPASSED'}
          </button>

          <div className="h-6 w-px bg-slate-800 mx-1" />

          <button
            type="button"
            onClick={() => handleTriggerAttack('spoof_sensor')}
            disabled={agentModePending}
            className="px-3 py-1.5 rounded text-xs font-medium bg-slate-900 hover:bg-slate-800 border border-slate-700 text-amber-300 disabled:cursor-wait disabled:opacity-60"
          >
            ⚡ Sim: Spoof Sensor
          </button>
          <button
            type="button"
            onClick={() => handleTriggerAttack('coordinated_intrusion')}
            disabled={agentModePending}
            className="px-3 py-1.5 rounded text-xs font-medium bg-slate-900 hover:bg-slate-800 border border-slate-700 text-rose-300 disabled:cursor-wait disabled:opacity-60"
          >
            ⚡ Sim: Coordinated Breach
          </button>
          <button
            type="button"
            onClick={() => handleTriggerAttack('prompt_injection')}
            disabled={agentModePending}
            className="px-3 py-1.5 rounded text-xs font-medium bg-slate-900 hover:bg-slate-800 border border-slate-700 text-purple-300 disabled:cursor-wait disabled:opacity-60"
          >
            ⚡ Sim: Prompt Injection
          </button>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7 space-y-6">
          <WingFloorplan devices={devices} />
          <AuditLogPanel entries={audit} />
        </div>

        <div className="lg:col-span-5 space-y-6">
          <ApprovalDrawer
            approvals={pendingApprovals}
            onDecision={handleDecision}
          />
          <IncidentFeed incidents={incidents} />
        </div>
      </div>
    </div>
  );
}
