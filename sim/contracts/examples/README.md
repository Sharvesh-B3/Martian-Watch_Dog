# Contract Examples

- `valid/` contains payloads that must pass their matching Draft 2020-12 schema.
- `invalid/` contains intentionally malformed or contract-incompatible payloads that must fail validation.
- A fixture's filename prefix selects its schema, as enforced by `../validate_examples.py`.

| Filename prefix | Schema |
|---|---|
| `telemetry_` | `telemetry.schema.json` |
| `presence_` | `presence.schema.json` |
| `attack_trigger_` | `attack_trigger.schema.json` |
| `attack_status_` | `attack_status.schema.json` |
| `injection_` | `injection.schema.json` |
| `control_` | `control.schema.json` |
| `control_ack_` | `control_ack.schema.json` |
| `decoy_input_` | `decoy_input.schema.json` |
| `decoy_event_` | `decoy_event.schema.json` |
| `ground_truth_` | `ground_truth.schema.json` |

The validator requires at least one valid and one invalid case for every schema. It uses format checking, so malformed UUIDs and RFC 3339 timestamps fail rather than being treated as annotations.

Invalid fixtures are test assets, not payload templates. Do not publish them to the lab except in explicit negative tests.
