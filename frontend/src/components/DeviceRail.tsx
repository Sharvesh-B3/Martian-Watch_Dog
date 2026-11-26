import { ChevronRight } from 'lucide-react';
import type { DeviceNode } from '../types/watchdog';
import {
  DEVICE_ORDER,
  DEVICE_VISUALS,
  keyMetric,
  metricLabel,
  metricValue,
  statusLabel,
} from './deviceVisuals';

interface Props {
  devices: DeviceNode[];
  selectedId: string | null;
  onSelect: (deviceId: string) => void;
}

export default function DeviceRail({ devices, selectedId, onSelect }: Props) {
  const ordered = [...devices].sort(
    (left, right) =>
      DEVICE_ORDER.indexOf(left.type) - DEVICE_ORDER.indexOf(right.type)
  );
  const selected = ordered.find((device) => device.id === selectedId) ?? null;

  return (
    <aside className="device-rail" aria-labelledby="devices-heading">
      <div className="section-heading-row">
        <div>
          <h2 id="devices-heading">Lab devices</h2>
          <p>{ordered.length} reporting now</p>
        </div>
      </div>

      <div className="device-list">
        {ordered.map((device) => {
          const visual = DEVICE_VISUALS[device.type];
          const Icon = visual.icon;
          const isSelected = selectedId === device.id;
          return (
            <button
              className="device-row"
              data-selected={isSelected}
              data-status={device.status}
              type="button"
              key={device.id}
              onClick={() => onSelect(device.id)}
              aria-pressed={isSelected}
            >
              <span className="device-row__icon" aria-hidden="true">
                <Icon size={19} />
              </span>
              <span className="device-row__copy">
                <strong className="device-row__full-name">{visual.label}</strong>
                <strong className="device-row__short-name">{visual.shortLabel}</strong>
                <span>{keyMetric(device)}</span>
              </span>
              <span className="device-row__state">
                <i aria-hidden="true" />
                {statusLabel(device.status)}
              </span>
              <ChevronRight className="device-row__chevron" aria-hidden="true" size={17} />
            </button>
          );
        })}
      </div>

      {selected && (
        <section className="device-detail" aria-labelledby="device-detail-heading">
          <div className="device-detail__head">
            <div>
              <span>{DEVICE_VISUALS[selected.type].label}</span>
              <h3 id="device-detail-heading">{selected.name}</h3>
            </div>
            <span className="state-label" data-status={selected.status}>
              {statusLabel(selected.status)}
            </span>
          </div>
          <dl>
            {Object.entries(selected.metrics).map(([key, value]) => (
              <div key={key}>
                <dt>{metricLabel(key)}</dt>
                <dd>{metricValue(key, value)}</dd>
              </div>
            ))}
          </dl>
          <p className="device-detail__updated">
            Updated {new Date(selected.last_updated).toLocaleTimeString()}
          </p>
        </section>
      )}
    </aside>
  );
}
