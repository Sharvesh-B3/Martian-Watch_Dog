export type DeviceStatus = 'normal' | 'warning' | 'quarantined' | 'decoy';

export type AttackCategory =
  | 'sensor_spoofing'
  | 'coordinated_intrusion'
  | 'prompt_injection'
  | 'anomalous_traffic';

export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'auto_executed';

export interface DeviceNode {
  id: string;                 // e.g., "smart_lock_01"
  name: string;               // e.g., "Bio-Lab Main Door"
  type: 'smart_lock' | 'rfid_scanner' | 'air_quality' | 'power_meter' | 'decoy_twin';
  zone: string;               // e.g., "Lab Wing A"
  status: DeviceStatus;
  metrics: Record<string, string | number | boolean>;
  last_updated: string;       // ISO timestamp
}

export interface Incident {
  id: string;
  timestamp: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  category: AttackCategory;
  title: string;
  plain_english_explanation: string; // The "Explain" step
  correlated_device_ids: string[];
  prompt_injection_detected: boolean;
  sanitized_excerpt?: string;        // Shows blocked injection payload if detected
  proposed_action: string;           // e.g., "Quarantine smart_lock_01 & route to Decoy Twin"
  approval_status: ApprovalStatus;
}

export interface ApprovalRequest {
  id: string;
  incident_id: string;
  created_at: string;
  target_device_id: string;
  recommended_action: string;
  risk_summary: string;
  status: 'pending' | 'approved' | 'rejected';
}

export interface AuditEntry {
  id: string;
  timestamp: string;
  actor: 'AI_AGENT' | 'HUMAN_OPERATOR' | 'GUARDRAIL' | 'SYSTEM';
  action: string;
  details: string;
}