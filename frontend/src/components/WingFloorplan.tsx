import type { DeviceNode } from '../types/watchdog';

const STATUS_STYLES: Record<DeviceNode['status'], string> = {
  normal: 'border-emerald-500/60 bg-emerald-950/20 text-emerald-300',
  warning: 'border-amber-500 bg-amber-950/30 text-amber-300 animate-pulse',
  quarantined: 'border-rose-500 bg-rose-950/40 text-rose-300',
  decoy: 'border-purple-500/70 bg-purple-950/30 text-purple-300',
};

interface Props {
  devices: DeviceNode[];
}

export default function WingFloorplan({ devices }: Props) {
  return (
    <section className="bg-slate-900/70 border border-slate-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
          Lab Wing A — Live Digital Twin Topology
        </h2>
        <span className="text-xs text-slate-400">{devices.length} Active Nodes</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {devices.map((dev) => (
          <div
            key={dev.id}
            className={`border rounded-lg p-4 transition ${STATUS_STYLES[dev.status]}`}
          >
            <div className="flex items-center justify-between">
              <span className="font-semibold text-sm text-white">{dev.name}</span>
              <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-black/40">
                {dev.status}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              {dev.id} • {dev.zone}
            </p>
            <div className="mt-3 pt-2 border-t border-white/10 flex flex-wrap gap-3 text-xs font-mono">
              {Object.entries(dev.metrics).map(([key, value]) => (
                <span key={key}>
                  {key}: <strong className="text-white">{String(value)}</strong>
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
