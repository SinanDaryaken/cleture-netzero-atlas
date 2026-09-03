# ADR 0036 — Central country registry and semantic geography roles

Status: Accepted  
Date: 2026-08-29

## Context

Factor sources use geography for different meanings: production origin, retail market,
calculation applicability, jurisdiction, grid or route endpoint. A missing origin had also
been rendered as `GLOBAL`, while country names embedded in free text were not consistently
resolved across languages. CONCITO makes the distinction visible: `Ra00327-DK` and
`Ra00327-ES` are Denmark/Spain retail-market variants, not evidence that bananas were grown
in those countries.

The suggested `bakrianoo/multilingual-lists` repository is a useful shape reference, but its
GitHub metadata declares no license and its last source commit is from 2015. Atlas therefore
must not vendor or depend on that dataset.

## Decision

1. `atlas_countries.code` (ISO-3166 alpha-2) is the canonical country identity. Alpha-3,
   numeric code, canonical English name and registry version are attributes. Source registry
   country fields reference this identity with a foreign key.
2. All translated names, official/common names, aliases and code spellings live in
   `atlas_country_labels` with language, source and review status. Initial data comes from
   pinned `pycountry 24.6.1` ISO/gettext catalogs; Atlas-specific aliases are explicit and
   versioned.
3. `/v1/countries` serves selectors. Free-text Catalog/Search queries resolve one
   unambiguous country label to a structured alpha-2 filter before concept/text search.
   Ambiguous two-letter words are ignored unless explicitly uppercase.
4. Canonical factors keep origin/applicability projections and additionally persist
   `geography_roles` with role, geography, derivation, source field, rule version and
   confidence.
5. CONCITO `Country` becomes `market`; origin remains unknown. WRAP `origin_region` becomes
   `production_origin` and `applicable_region` becomes `calculation_applicability`.
6. Unknown is never displayed or indexed as global. `GLOBAL` is valid only when the source
   or an approved mapping explicitly says global.

## Consequences

- `banana DK`, `banana Denmark`, `banana Danimarka`, `banana Dänemark` and `banana 丹麦`
  resolve to the same DK market filter.
- Country variants remain usable without contaminating production-origin semantics.
- New languages and aliases can be reviewed centrally without changing source adapters or
  factor IDs.
- Region/grid/custom geography remains in the existing versioned geography graph; the
  country registry owns country identity and labels, not fallback policy.
