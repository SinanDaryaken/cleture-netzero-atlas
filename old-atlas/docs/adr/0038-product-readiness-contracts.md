# ADR 0038 — Product readiness contracts

## Status

Accepted — 2026-08-30

## Decision

Atlas product inputs that are not source factors are first-class, reviewed records:

- facilities live in `atlas_facilities` and are resolved by `facility_id` before recommendation;
- conditional unit bridges may consume only active, effective and approved records from
  `atlas_conversion_parameters`; facility-specific values precede country and global values;
- canonical regression executions, results and owner decisions live in
  `atlas_regression_runs`, `atlas_regression_results` and `atlas_regression_reviews`;
- `/health` remains a liveness endpoint, while `/ready` is the product gate and returns 503 until
  intelligence, recommendation and sector coverage are all ready;
- licensed official artifacts are declared in `config/official-snapshots.yaml`. Public CI runs
  synthetic/unit and live canonical regression checks; a labelled self-hosted runner holds the
  licensed snapshots and runs their dedicated workflow.

The Explorer reads facilities from `/v1/facilities`; it does not own a parallel facility list.
Conversion parameters start as drafts and require an explicit approve/reject action. Regression
changes likewise require an auditable owner decision. No review gate is inferred from a passing
process health check.

## Consequences

Product consumers can persist stable facility and regression identities. Conditional conversions
gain dated provenance without embedding operational assumptions in code or requests. Deployments
can distinguish a running service from a product-ready dataset. Licensed artifacts stay outside
Git while their required paths, hashes at execution time and parser contract tests remain explicit.

Translation drafts remain outside this ADR's automatic paths: generation may be incremental, but
all target-language preferred labels and search alternatives still require human review before the
intelligence readiness gate can pass.
