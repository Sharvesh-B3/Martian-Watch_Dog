import { useEffect, useMemo, useState } from 'react';
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
  type StreamStatus,
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

function mergeWithLive<T extends { id: string }>(incoming: T[], live: T[]): T[] {
  const liveIds = new Set(live.map((item) => item.id));
  return [...live, ...incoming.filter((item) => !liveIds.has(item.id))];
}

function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : 'Unexpected request failure';
}

function modeFromAudit(entries: AuditEntry[]): boolean | null {
  const modeEntry = entries.find(
    (entry) =>
      entry.action === 'AGENT_ACTIVATED' || entry.action === 'AGENT_BYPASSED'
  );
  if (!modeEntry) return null;
  return modeEntry.action === 'AGENT_ACTIVATED';
}

export function useWatchdog() {
  const [devices, setDevices] = useState<DeviceNode[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [agentEnabled, setAgentEnabled] = useState(true);
  const [streamStatus, setStreamStatus] = useState<StreamStatus>(
    USE_MOCK_DATA ? 'mock' : 'connecting'
  );
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [agentModePending, setAgentModePending] = useState(false);
  const [simulationPending, setSimulationPending] = useState<AttackType | null>(
    null
  );
  const [decisionPending, setDecisionPending] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;

    const handleEvent = (event: StreamEvent) => {
      if (!active) return;
      switch (event.type) {
        case 'device_update':
          setDevices((previous) => upsertById(previous, event.device));
          break;
        case 'new_incident':
          setIncidents((previous) => upsertById(previous, event.incident));
          break;
        case 'new_approval':
          setApprovals((previous) => upsertById(previous, event.approval));
          break;
        case 'audit_entry':
          setAudit((previous) => upsertById(previous, event.entry));
          if (event.entry.action === 'AGENT_ACTIVATED') setAgentEnabled(true);
          if (event.entry.action === 'AGENT_BYPASSED') setAgentEnabled(false);
          break;
      }
    };

    const unsubscribe = subscribeToStream(handleEvent, (status) => {
      if (active) setStreamStatus(status);
    });

    setLoading(true);
    setLoadError(null);
    void fetchDashboardState()
      .then((data) => {
        if (!active) return;
        setDevices((previous) => mergeWithLive(data.devices, previous));
        setIncidents((previous) => mergeWithLive(data.incidents, previous));
        setApprovals((previous) => mergeWithLive(data.approvals, previous));
        setAudit((previous) => mergeWithLive(data.audit, previous));
        const knownMode = modeFromAudit(data.audit);
        if (knownMode !== null) setAgentEnabled(knownMode);
      })
      .catch((error: unknown) => {
        if (active) setLoadError(messageFrom(error));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      unsubscribe();
    };
  }, [reloadKey]);

  const pendingApprovals = useMemo(
    () => approvals.filter((approval) => approval.status === 'pending'),
    [approvals]
  );
  const activeApproval = pendingApprovals[0] ?? null;
  const activeIncident = useMemo(() => {
    if (activeApproval) {
      return (
        incidents.find((incident) => incident.id === activeApproval.incident_id) ??
        incidents[0] ??
        null
      );
    }
    return incidents[0] ?? null;
  }, [activeApproval, incidents]);

  const toggleAgent = async () => {
    const next = !agentEnabled;
    setAgentModePending(true);
    setActionError(null);
    try {
      const response = await setAgentMode(next);
      setAgentEnabled(response.enabled);
    } catch (error: unknown) {
      setActionError(`Agent mode was not changed. ${messageFrom(error)}`);
      throw error;
    } finally {
      setAgentModePending(false);
    }
  };

  const triggerAttack = async (attackType: AttackType) => {
    setSimulationPending(attackType);
    setActionError(null);
    try {
      await triggerSimAttack(attackType);
    } catch (error: unknown) {
      setActionError(`Simulation did not start. ${messageFrom(error)}`);
      throw error;
    } finally {
      setSimulationPending(null);
    }
  };

  const decide = async (
    approval: ApprovalRequest,
    decision: ApprovalDecision
  ) => {
    setDecisionPending(approval.id);
    setActionError(null);
    try {
      await decideApproval(approval.id, decision);
      setApprovals((previous) =>
        previous.map((item) =>
          item.id === approval.id ? { ...item, status: decision } : item
        )
      );
      setIncidents((previous) =>
        previous.map((incident) =>
          incident.id === approval.incident_id
            ? { ...incident, approval_status: decision }
            : incident
        )
      );
    } catch (error: unknown) {
      setActionError(`Decision was not recorded. ${messageFrom(error)}`);
      throw error;
    } finally {
      setDecisionPending(null);
    }
  };

  return {
    devices,
    incidents,
    approvals,
    audit,
    pendingApprovals,
    activeApproval,
    activeIncident,
    agentEnabled,
    streamStatus,
    loading,
    loadError,
    actionError,
    agentModePending,
    simulationPending,
    decisionPending,
    retry: () => setReloadKey((key) => key + 1),
    dismissActionError: () => setActionError(null),
    toggleAgent,
    triggerAttack,
    decide,
  };
}
