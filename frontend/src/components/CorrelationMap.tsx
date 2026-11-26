import type { DeviceNode } from '../types/watchdog';
import { DEVICE_ORDER, DEVICE_VISUALS, statusLabel } from './deviceVisuals';

interface Props {
  devices: DeviceNode[];
  correlatedIds: string[];
  selectedId: string | null;
  onSelect: (deviceId: string) => void;
}

const POSITIONS: Record<DeviceNode['type'], { x: number; y: number }> = {
  smart_lock: { x: 21, y: 28 },
  rfid_scanner: { x: 21, y: 72 },
  air_quality: { x: 76, y: 24 },
  power_meter: { x: 76, y: 68 },
  decoy_twin: { x: 50, y: 50 },
};

const LINKS: [DeviceNode['type'], DeviceNode['type']][] = [
  ['smart_lock', 'rfid_scanner'],
  ['smart_lock', 'power_meter'],
  ['air_quality', 'power_meter'],
  ['power_meter', 'decoy_twin'],
];

export default function CorrelationMap({
  devices,
  correlatedIds,
  selectedId,
  onSelect,
}: Props) {
  const byType = new Map(devices.map((device) => [device.type, device]));
  const correlated = new Set(correlatedIds);

  return (
    <div
      className="correlation-map"
      role="group"
      data-ui="correlation-map"
      data-diagram="hub-tools"
      aria-label="Live relationship map for five campus IoT devices"
    >
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {DEVICE_ORDER.map((type) => {
          const position = POSITIONS[type];
          return <circle key={type} cx={position.x} cy={position.y} r="7" />;
        })}
        {LINKS.map(([fromType, toType]) => {
          const from = POSITIONS[fromType];
          const to = POSITIONS[toType];
          const fromDevice = byType.get(fromType);
          const toDevice = byType.get(toType);
          const active = Boolean(
            fromDevice &&
              toDevice &&
              correlated.has(fromDevice.id) &&
              correlated.has(toDevice.id)
          );
          const decoyRoute = Boolean(
            toDevice?.type === 'decoy_twin' &&
              Number(toDevice.metrics.active_traps ?? 0) > 0
          );
          return (
            <line
              key={`${fromType}-${toType}`}
              x1={from.x}
              y1={from.y}
              x2={to.x}
              y2={to.y}
              data-active={active || decoyRoute}
            />
          );
        })}
      </svg>

      {DEVICE_ORDER.map((type) => {
        const device = byType.get(type);
        if (!device) return null;
        const position = POSITIONS[type];
        const visual = DEVICE_VISUALS[type];
        const Icon = visual.icon;
        const isCorrelated = correlated.has(device.id);
        return (
          <button
            className="map-node"
            data-status={device.status}
            data-correlated={isCorrelated}
            data-selected={selectedId === device.id}
            style={{ left: `${position.x}%`, top: `${position.y}%` }}
            type="button"
            key={device.id}
            onClick={() => onSelect(device.id)}
            aria-label={`${device.name}: ${statusLabel(device.status)}`}
          >
            <span aria-hidden="true">
              <Icon size={21} />
            </span>
            <strong>{visual.shortLabel}</strong>
            <i aria-hidden="true" />
          </button>
        );
      })}
    </div>
  );
}
