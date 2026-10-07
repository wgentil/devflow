---
name: migrate
description: Compare legacy requirements and ordered migration increments with explicit parity evidence.
---

# Migration parity

Map each legacy rule to requirement IDs and parity criteria. Preserve gaps, contradictions, and authorized waivers with their rationale and cost if wrong. Keep increment dependencies acyclic and block later delivery until prerequisites are delivered.

Use `migrate store/record-parity/bind` with a control root and explicit operation ID. Bind runs to increments before delivery so predecessor/parity guards participate in terminal recording. Resume through `migrate inspect`; do not submit caller-edited state. See `../../docs/journal-integration.md`.
