import { useEffect, useState } from 'react';
import { LoaderCircle, Server, ShieldAlert } from 'lucide-react';
import { DEMO_CONTROLS_ENABLED } from '../api/client';
import ActivityDrawer from '../components/ActivityDrawer';
import AppHeader from '../components/AppHeader';
import ConnectionNotice from '../components/ConnectionNotice';
import ContainmentProof from '../components/ContainmentProof';
import DecisionPanel from '../components/DecisionPanel';
import DeviceDetailPanel from '../components/DeviceDetailPanel';
import DeviceRail from '../components/DeviceRail';
import SimulationMenu from '../components/SimulationMenu';
import ThreatWorkspace from '../components/ThreatWorkspace';
import { useWatchdog } from '../hooks/useWatchdog';

export default function CommandCenter() {
  const watchdog = useWatchdog();
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const [openPanel, setOpenPanel] = useState<
    'activity' | 'simulation' | 'device' | null
  >(null);
  const [mobileView, setMobileView] = useState<'threat' | 'devices'>('threat');

  useEffect(() => {
    if (watchdog.devices.length === 0) return;
    if (
      selectedDeviceId &&
      watchdog.devices.some((device) => device.id === selectedDeviceId)
    ) {
      return;
    }
    const priority =
      watchdog.devices.find((device) => device.status === 'quarantined') ??
      watchdog.devices.find((device) => device.status === 'warning') ??
      watchdog.devices[0];
    setSelectedDeviceId(priority.id);
  }, [selectedDeviceId, watchdog.devices]);

  const liveAnnouncement = watchdog.activeIncident
    ? `Incident updated. ${
        watchdog.activeApproval ? 'Operator decision required.' : ''
      }`
    : 'No active incident.';

  const selectedDevice =
    watchdog.devices.find((device) => device.id === selectedDeviceId) ?? null;
  const decoyDevice =
    watchdog.devices.find((device) => device.id === 'decoy_twin_01') ?? null;
  const rerouteConfirmed =
    decoyDevice?.metrics.route_target === 'decoy' &&
    decoyDevice.metrics.route_confirmed === true;
  const panelApproval = watchdog.activeApproval ?? watchdog.approvals[0] ?? null;

  const selectDevice = (deviceId: string, moveToDevices = false) => {
    setSelectedDeviceId(deviceId);
    if (moveToDevices) setMobileView('devices');
    if (window.matchMedia('(max-width: 1199px)').matches) {
      setOpenPanel('device');
    }
  };

  return (
    <div className="app-shell">
      <AppHeader
        streamStatus={watchdog.streamStatus}
        agentEnabled={watchdog.agentEnabled}
        deviceCount={watchdog.devices.length}
        demoControlsEnabled={DEMO_CONTROLS_ENABLED}
        onOpenActivity={() => setOpenPanel('activity')}
        onOpenSimulation={() => setOpenPanel('simulation')}
      />

      <p className="sr-only" aria-live="polite">
        {liveAnnouncement}
      </p>

      <main id="top">
        <section
          className="operations section"
          id="operations"
          data-mobile-view={mobileView}
          data-has-decision="true"
        >
          <div className="app-wrap wrap">
          <ConnectionNotice
            loadError={watchdog.loadError}
            actionError={watchdog.actionError}
            streamStatus={watchdog.streamStatus}
            onRetry={watchdog.retry}
            onDismissActionError={watchdog.dismissActionError}
          />

          {watchdog.loading && watchdog.devices.length === 0 ? (
            <section className="loading-state" aria-label="Connecting to lab">
              <LoaderCircle aria-hidden="true" size={24} />
              <h2>Connecting to the lab</h2>
              <p>Loading devices, incidents and operator decisions.</p>
            </section>
          ) : (
            <div
              className="operations-grid"
              data-has-decision="true"
              data-mobile-view={mobileView}
            >
              <div className="mobile-view-switch" role="tablist" aria-label="Operations view">
                <button
                  type="button"
                  role="tab"
                  aria-selected={mobileView === 'threat'}
                  onClick={() => setMobileView('threat')}
                >
                  <ShieldAlert aria-hidden="true" size={17} />
                  Threat
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={mobileView === 'devices'}
                  onClick={() => setMobileView('devices')}
                >
                  <Server aria-hidden="true" size={17} />
                  Devices
                </button>
              </div>

              <DeviceRail
                devices={watchdog.devices}
                selectedId={selectedDeviceId}
                onSelect={(deviceId) => selectDevice(deviceId)}
              />

              <ThreatWorkspace
                incident={watchdog.activeIncident}
                devices={watchdog.devices}
                selectedDeviceId={selectedDeviceId}
                onSelectDevice={(deviceId) => selectDevice(deviceId, true)}
              />

              <div className="right-rail">
                {panelApproval ? (
                  <DecisionPanel
                    approval={panelApproval}
                    devices={watchdog.devices}
                    pending={
                      panelApproval.status === 'pending' &&
                      watchdog.decisionPending === panelApproval.id
                    }
                    replayPending={
                      watchdog.simulationPending === 'coordinated_intrusion'
                    }
                    canReplay={watchdog.agentEnabled}
                    onDecision={watchdog.decide}
                    onReplay={() =>
                      watchdog.triggerAttack('coordinated_intrusion')
                    }
                  />
                ) : (
                  <aside
                    className="decision-panel decision-panel--idle"
                    aria-labelledby="decision-heading"
                  >
                    <div className="decision-panel__icon" aria-hidden="true">
                      <ShieldAlert size={23} />
                    </div>
                    <span className="section-kicker">Human approval standby</span>
                    <h2 id="decision-heading">No decision required</h2>
                    <p className="decision-panel__copy">
                      High-risk containment requests will appear here with full
                      context before any action executes.
                    </p>
                  </aside>
                )}
                {rerouteConfirmed && decoyDevice && (
                  <ContainmentProof decoy={decoyDevice} />
                )}
              </div>
            </div>
          )}
          </div>
        </section>
      </main>

      <ActivityDrawer
        open={openPanel === 'activity'}
        incidents={watchdog.incidents}
        audit={watchdog.audit}
        onClose={() => setOpenPanel(null)}
      />

      <SimulationMenu
        open={openPanel === 'simulation'}
        agentEnabled={watchdog.agentEnabled}
        agentModePending={watchdog.agentModePending}
        simulationPending={watchdog.simulationPending}
        resetPending={watchdog.resetPending}
        onClose={() => setOpenPanel(null)}
        onToggleAgent={watchdog.toggleAgent}
        onTrigger={watchdog.triggerAttack}
        onReset={watchdog.resetSimulation}
      />

      <DeviceDetailPanel
        open={openPanel === 'device'}
        device={selectedDevice}
        onClose={() => setOpenPanel(null)}
      />
    </div>
  );
}
