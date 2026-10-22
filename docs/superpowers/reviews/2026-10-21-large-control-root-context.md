# Large control root context — verification report

Status: scale evidence recorded; final suite and independent review pending.

## Actual local scale benchmark

Measured on 2026-10-21 using the approved disposable benchmark, production
implementation `c1ffd59`. This is synthetic history, not the reporter project.
The fixture appends valid events to its own fresh journal and finishes with full
authoritative replay. Historical delivered metadata and long review strings do
not claim completed live verifier deliveries. No customer roots were touched.

```json
{
  "attempt_count": 1,
  "commit_ms": 608.8972080033273,
  "component_bytes": {
    "artifact_references": 311,
    "control_envelope": 852,
    "governing": 0,
    "optional": 0,
    "requirements": 115,
    "serialization_overhead": 2302,
    "serialized_bytes": 16194,
    "shared_spec": 466,
    "stage_documents": 12148
  },
  "environment": {
    "platform": "macOS-27.0.1-arm64-arm-64bit-Mach-O",
    "python": "3.14.7"
  },
  "exact_retry_ms": 1696.4986670063809,
  "exact_retry_same_token": true,
  "fixture": {
    "delivered_runs": 40,
    "events": 4370,
    "journal_bytes": 80249749,
    "state_bytes": 79706957
  },
  "initial_replay_ms": 1530.7722080033273,
  "limitations": [
    "Synthetic delivered metadata and long review strings, not the reporter project or live verifier deliveries.",
    "total_ms measures actual CLI next including locked commit; preparation.total_ms covers fewer phases.",
    "Ordinary authoritative journal replay remains proportional to history; no paid host or native Windows validation."
  ],
  "preflight_ms": 1315,
  "replay_counts": {
    "exact_retry": 1,
    "initial": 1,
    "next": 2,
    "worker": 0
  },
  "selected_context_bytes": 14620,
  "selected_units_match_small": true,
  "small_selected_context_bytes": 14620,
  "token_issued": true,
  "total_ms": 2121.5713750571012,
  "worker_ms": 141
}
```

The selected task matched the small fixture. The default 20,000-byte context
budget, five-second worker deadline and 8,192-byte hook envelope remain unchanged.
The whole CLI includes the final locked journal replay, while the view timing
fields cover preflight and worker only. Ordinary replay cost still grows with
history; there is no checkpoint/archive redesign in this fix. One local result
cannot establish speed on the reporter’s project or other platforms.
