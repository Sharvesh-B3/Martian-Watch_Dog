import { Bot, DoorOpen, FlaskConical, RotateCcw, ShieldBan, Wind } from 'lucide-react';
import type { AttackType } from '../api/client';
import SidePanel from './SidePanel';

interface Props {
  open: boolean;
  agentEnabled: boolean;
  agentModePending: boolean;
  simulationPending: AttackType | null;
  resetPending: boolean;
  onClose: () => void;
  onToggleAgent: () => Promise<void>;
  onTrigger: (attackType: AttackType) => Promise<void>;
  onReset: () => Promise<void>;
}

const SCENARIOS: Array<{
  type: AttackType;
  title: string;
  description: string;
  icon: typeof Wind;
}> = [
  {
    type: 'spoof_sensor',
    title: 'Trigger sensor spoofing',
    description: 'Publishes implausible air readings for automatic filtering.',
    icon: Wind,
  },
  {
    type: 'coordinated_intrusion',
    title: 'Trigger coordinated intrusion',
    description: 'Combines CCTV loss, a forced unlock and an outbound scan.',
    icon: DoorOpen,
  },
  {
    type: 'prompt_injection',
    title: 'Trigger prompt injection',
    description: 'Places an instruction override inside untrusted sensor metadata.',
    icon: ShieldBan,
  },
];

export default function SimulationMenu({
  open,
  agentEnabled,
  agentModePending,
  simulationPending,
  resetPending,
  onClose,
  onToggleAgent,
  onTrigger,
  onReset,
}: Props) {
  const toggleAgent = () => {
    void onToggleAgent().catch(() => undefined);
  };

  const trigger = (type: AttackType) => {
    void onTrigger(type).catch(() => undefined);
  };

  const reset = () => {
    void onReset().catch(() => undefined);
  };

  return (
    <SidePanel
      open={open}
      title="Simulation"
      description="Lab-only controls for synthetic attacks and comparison runs."
      onClose={onClose}
    >
      <section className="agent-control" aria-labelledby="agent-control-heading">
        <div className="agent-control__icon" aria-hidden="true">
          <Bot size={21} />
        </div>
        <div>
          <h3 id="agent-control-heading">Watchdog Agent</h3>
          <p>
            {agentEnabled
              ? 'Active. Correlation, reasoning and containment policy are running.'
              : 'Bypassed. Attacks are recorded without reasoning or containment.'}
          </p>
        </div>
        <button
          className="button button--secondary button--wide"
          type="button"
          disabled={agentModePending || simulationPending !== null}
          onClick={toggleAgent}
        >
          {agentEnabled ? 'Bypass agent' : 'Activate agent'}
        </button>
        <button
          className="button button--secondary button--wide"
          type="button"
          disabled={resetPending || agentModePending || simulationPending !== null}
          onClick={reset}
        >
          <RotateCcw aria-hidden="true" size={17} />
          {resetPending ? 'Resetting lab' : 'Reset lab'}
        </button>
      </section>

      <section className="scenario-list" aria-labelledby="scenario-heading">
        <div className="scenario-list__heading">
          <FlaskConical aria-hidden="true" size={18} />
          <h3 id="scenario-heading">Synthetic scenarios</h3>
        </div>
        {SCENARIOS.map((scenario) => {
          const Icon = scenario.icon;
          const pending = simulationPending === scenario.type;
          return (
            <button
              className="scenario-button"
              type="button"
              key={scenario.type}
              disabled={agentModePending || simulationPending !== null}
              onClick={() => trigger(scenario.type)}
            >
              <span aria-hidden="true">
                <Icon size={20} />
              </span>
              <span>
                <strong>{pending ? 'Starting scenario' : scenario.title}</strong>
                <small>{scenario.description}</small>
              </span>
            </button>
          );
        })}
      </section>
    </SidePanel>
  );
}
