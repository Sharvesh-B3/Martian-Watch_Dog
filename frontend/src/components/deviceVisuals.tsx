import {
  Fan,
  Gauge,
  LockKeyhole,
  Radar,
  ScanLine,
  type LucideIcon,
} from 'lucide-react';
import type { DeviceNode } from '../types/watchdog';

interface DeviceVisual {
  label: string;
  shortLabel: string;
  icon: LucideIcon;
}

export const DEVICE_ORDER: DeviceNode['type'][] = [
  'smart_lock',
  'rfid_scanner',
  'air_quality',
  'power_meter',
  'decoy_twin',
];

export const DEVICE_VISUALS: Record<DeviceNode['type'], DeviceVisual> = {
  smart_lock: {
    label: 'Smart lock',
    shortLabel: 'Lock',
    icon: LockKeyhole,
  },
  rfid_scanner: {
    label: 'RFID reader',
    shortLabel: 'RFID',
    icon: ScanLine,
  },
  air_quality: {
    label: 'Air quality',
    shortLabel: 'Air',
    icon: Fan,
  },
  power_meter: {
    label: 'Power meter',
    shortLabel: 'Power',
    icon: Gauge,
  },
  decoy_twin: {
    label: 'Decoy Twin',
    shortLabel: 'Decoy',
    icon: Radar,
  },
};

export function statusLabel(status: DeviceNode['status']): string {
  if (status === 'quarantined') return 'Quarantined';
  if (status === 'warning') return 'Needs review';
  if (status === 'decoy') return 'Decoy ready';
  return 'Healthy';
}

export function keyMetric(device: DeviceNode): string {
  if (device.type === 'smart_lock') {
    return device.metrics.locked === false ? 'Unlocked' : 'Locked';
  }
  if (device.type === 'rfid_scanner') {
    const badge = device.metrics.last_badge;
    return badge && badge !== 'NONE' ? String(badge) : 'Reader idle';
  }
  if (device.type === 'air_quality') {
    return `${device.metrics.co2_ppm ?? '—'} ppm CO₂`;
  }
  if (device.type === 'power_meter') {
    return `${device.metrics.outbound_conns ?? '—'} connections`;
  }
  return `${device.metrics.captured_payloads ?? 0} captured`;
}

export function metricLabel(key: string): string {
  const known: Record<string, string> = {
    co2_ppm: 'CO₂',
    pm25: 'PM2.5',
    temp_c: 'Temperature',
    load_kw: 'Load',
    active_traps: 'Active traps',
    captured_payloads: 'Captured payloads',
    last_payload_hash: 'Last payload hash',
    last_source: 'Last source',
    last_command: 'Last command',
    route_target: 'Gateway target',
    route_confirmed: 'Route confirmed',
    upstream: 'Gateway upstream',
    active_sessions: 'Active sessions',
    connection_count: 'Gateway connections',
    attacker_reconnects: 'Attacker reconnects',
    switch_count: 'Route switches',
    real_bytes: 'Real-broker bytes',
    decoy_bytes: 'Decoy-broker bytes',
    last_switch_at: 'Last route switch',
    incident_id: 'Route incident',
    last_error: 'Gateway error',
    last_badge: 'Last badge',
    scan_rate_per_min: 'Scans per minute',
    outbound_conns: 'Outbound connections',
    door_closed: 'Door closed',
    failed_attempts: 'Failed attempts',
  };
  return known[key] ?? key.replaceAll('_', ' ');
}

export function metricValue(key: string, value: string | number | boolean): string {
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (key === 'temp_c') return `${value} °C`;
  if (key === 'load_kw') return `${value} kW`;
  if (key === 'real_bytes' || key === 'decoy_bytes') return `${value} B`;
  return String(value);
}
