import type { DeviceNode } from '../types/watchdog';
import SidePanel from './SidePanel';
import {
  DEVICE_VISUALS,
  metricLabel,
  metricValue,
  statusLabel,
} from './deviceVisuals';

interface Props {
  open: boolean;
  device: DeviceNode | null;
  onClose: () => void;
}

export default function DeviceDetailPanel({ open, device, onClose }: Props) {
  if (!device) return null;
  const visual = DEVICE_VISUALS[device.type];
  const Icon = visual.icon;

  return (
    <SidePanel
      open={open}
      title={device.name}
      description={`${visual.label}. ${statusLabel(device.status)}.`}
      onClose={onClose}
    >
      <div className="drawer-device-state" data-status={device.status}>
        <span aria-hidden="true">
          <Icon size={22} />
        </span>
        <div>
          <strong>{statusLabel(device.status)}</strong>
          <small>{device.id}</small>
        </div>
      </div>
      <dl className="drawer-metrics">
        {Object.entries(device.metrics).map(([key, value]) => (
          <div key={key}>
            <dt>{metricLabel(key)}</dt>
            <dd>{metricValue(key, value)}</dd>
          </div>
        ))}
      </dl>
      <p className="drawer-updated">
        Last update {new Date(device.last_updated).toLocaleTimeString()}
      </p>
    </SidePanel>
  );
}
