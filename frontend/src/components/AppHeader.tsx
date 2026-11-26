import {
  Activity,
  FlaskConical,
  ShieldCheck,
  Wifi,
  WifiOff,
} from 'lucide-react';
import type { StreamStatus } from '../api/client';

interface Props {
  streamStatus: StreamStatus;
  agentEnabled: boolean;
  deviceCount: number;
  demoControlsEnabled: boolean;
  onOpenActivity: () => void;
  onOpenSimulation: () => void;
}

const CONNECTION_COPY: Record<StreamStatus, string> = {
  mock: 'Mock lab',
  connecting: 'Connecting',
  live: 'Live backend',
  reconnecting: 'Reconnecting',
  offline: 'Offline',
};

export default function AppHeader({
  streamStatus,
  agentEnabled,
  deviceCount,
  demoControlsEnabled,
  onOpenActivity,
  onOpenSimulation,
}: Props) {
  const ConnectionIcon =
    streamStatus === 'offline' || streamStatus === 'reconnecting' ? WifiOff : Wifi;

  return (
    <header className="app-header nav" data-enter>
      <div className="app-wrap wrap app-header__inner">
        <a className="skip-link" href="#top">
          Skip to operations
        </a>

        <div className="brand-block">
          <span className="brand-mark" aria-hidden="true">
            A
          </span>
          <div>
            <span className="brand-name">Aegis Watchdog</span>
            <span className="console-title">Campus IoT security console</span>
          </div>
        </div>

        <div className="header-facts" aria-label="System status">
          <span className="status-readout" data-state={streamStatus}>
            <ConnectionIcon aria-hidden="true" size={16} />
            {CONNECTION_COPY[streamStatus]}
          </span>
          <span className="status-readout" data-state={agentEnabled ? 'active' : 'bypassed'}>
            <ShieldCheck aria-hidden="true" size={16} />
            Agent {agentEnabled ? 'active' : 'bypassed'}
          </span>
          <span className="header-fact">{deviceCount} devices · 60-second correlation</span>
        </div>

        <nav className="header-actions" aria-label="Console tools">
          <button className="button button--secondary" type="button" onClick={onOpenActivity}>
            <Activity aria-hidden="true" size={17} />
            View activity
          </button>
          {demoControlsEnabled && (
            <button className="button button--primary" type="button" onClick={onOpenSimulation}>
              <FlaskConical aria-hidden="true" size={17} />
              Start simulation
            </button>
          )}
        </nav>
      </div>
    </header>
  );
}
