# ADR 0014 — Environmental entity semantics

## Status

Accepted — 2026-08-28

## Context

Atlas sources no longer contain only direct emission factors. National inventory tables
mix activity data, emissions, implied factors and calculation parameters. LCA databases
publish characterized results and lifecycle modules. Cloud coefficient engines publish
usage conversions, technical properties and embodied-emission coefficients.

Flattening these records into an undifferentiated emission-factor type would make matching
unsafe and erase the calculation/provenance boundary.

## Decision

Canonical numeric records carry an explicit `entity_type` independent from gas/value
semantics (`factor_value_kind`) and intended use. Existing factor tables remain the
backward-compatible persistence surface during this phase, but their records are treated
as typed environmental entities.

Default matching is limited to direct and implied emission factors that also satisfy the
existing CO2e-total and inventory-use requirements. Other entity types remain queryable
through the API but cannot silently enter calculations.

Source history distinguishes targeted annual releases/submissions from snapshot-based API
time series, versioned databases and derived-data releases. Only targeted annual sources
accept a year-specific backfill run.

## Consequences

- New source parsers must classify every normalized numeric record.
- API consumers can filter by `entity_type`.
- Existing records migrate to `emission_factor` without losing compatibility.
- A future physical table rename can occur without changing the semantic contract.
