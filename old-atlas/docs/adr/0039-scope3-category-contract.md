# ADR 0039 — GHG Protocol Scope 3 category contract

## Status

Accepted — 2026-08-30

## Decision

`corporate_carbon.ghg_protocol.scope3` is category-aware. A recommendation request carries
`activity.scope3_category` as an integer from 1 through 15. The category is part of the
recommendation intent, candidate applicability, reason codes and trace; it is not an
unstructured search term.

The versioned recommendation policy owns the 15-category registry. Each category declares its
upstream/downstream direction, supported calculation methods, required inputs, current
availability and compatible recommendation families. `GET /v1/scope3/categories` and the Scope 3
profile rules expose the same policy data used by the engine.

Strict mode always requires an explicit category. Suggest mode may infer a category only when the
resolved activity family maps to exactly one category, and records that inference as an
assumption. Multi-category families never guess direction: road freight requires category 4 or 9,
and waste requires category 5 or 12. An explicit incompatible category fails before candidate
ranking with a `family_category_mismatch` trace.

Category selection does not replace activity detail. Waste categories 5 and 12 require explicit
material and treatment qualifiers; business travel category 6 requires a haul class. Missing
values return `needs_input`, preventing a generic waste or flight query from selecting an
arbitrary material or distance class.

Scope 1 combustion and Scope 2 generation factors are not relabelled as Scope 3. Category 3 may
select only factors whose published/projected scope is Scope 3, such as well-to-tank records.
Unsupported categories remain visible as explicit coverage gaps instead of silently falling back
to an unrelated factor family.

## Consequences

Consumers can store a stable GHG Protocol category beside the selected factor and distinguish
upstream from downstream use of otherwise similar transport or waste factors. Explorer presents
the category selector only for Scope 3. Current partial or unsupported categories are discoverable
before a calculation request, giving source-integration work an explicit backlog rather than an
ambiguous “no factor” result.
