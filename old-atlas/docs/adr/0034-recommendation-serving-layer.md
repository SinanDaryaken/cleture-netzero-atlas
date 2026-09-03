# ADR-0034 — Country-aware recommendation serving layer

## Status

Accepted — 2026-08-29

## Decision

Published source factors remain immutable source facts. Product selection metadata is a
separate, rebuildable projection in `atlas_factor_applicabilities`, with factor lineage in
`atlas_factor_relationships` and versioned country/profile/family fallback order in
`atlas_fallback_policies`.

Products use `POST /v1/recommendations`. Catalog and developer discovery may continue to use
`POST /v1/search`; `/v1/match` and `/v1/resolve` are removed. Recommendation hard-gates concept,
calculation role, profile/scope, boundary qualifiers and unit path before lexicographic ranking.
A conditional unit path remains selectable and returns `conversion_parameter_required`.

Ranking is jurisdictional. The key is country + calculation profile + factor family. An exact
country factor precedes regional and global data. Named national authorities are declarative
overrides (for example ETKB/TR, EPA/US, DEFRA/GB); an unlisted ISO country uses the generic
exact-country → regional → global hierarchy. A foreign-country factor is never silently used:
the caller must send `accept_proxy=true` and persist that decision.

`suggest` mode may apply a declared, auditable assumption. `strict` mode returns `needs_input`
when a material qualifier is missing. Electricity connection level is the first implementation:
suggest assumes distribution and reports it; strict asks distribution vs transmission.

Runtime selection has no license gate. License and distribution review remain ingestion/publish
responsibilities; every published factor visible to this internal serving layer is accessible.

When a logical factor has annual versions, the serving projection keeps the version closest to
the requested reporting year; an equal-distance tie prefers the past year. A factor with no
publisher-declared reference year remains eligible as a methodology default, but it is explicitly
labelled `UNDATED` and never presented as if it belonged to the requested reporting year.

## Consequences

- Source normalizers and historical rows are not rewritten when recommendation policy changes.
- Projection rebuild/check commands are idempotent and container startup only rebuilds on a
  missing or stale policy version.
- A single synthetic confidence percentage is not authoritative. Responses expose grade, tier,
  ordered rank dimensions, assumptions, conversion and trace.
- Core V1 covers gasoline, natural gas, diesel, electricity, refrigerants, road freight, air travel,
  waste and purchased services.
