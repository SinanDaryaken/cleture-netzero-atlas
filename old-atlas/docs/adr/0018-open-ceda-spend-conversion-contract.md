# ADR 0018 — Open CEDA spend conversion contract

## Status

Accepted — 2026-08-28

## Context

Open CEDA publishes spend-based greenhouse-gas intensities in model-base-year US dollars
at producer prices. A user's nominal local-currency purchaser-price spend is therefore not
directly compatible with the published factor. The workbooks also contain exchange-rate,
purchaser/producer conversion and sector price-index tables alongside the factor matrices.
Flattening all numeric cells into emission factors would create dimensionally invalid
results and hide the calculation inputs required for a reproducible conversion.

The 2025 release additionally publishes country-modelled, Rest of World and regional
average matrices. These geography variants have different applicability semantics and
cannot be treated as interchangeable global factors.

## Decision

- Country and regional factor matrices become canonical `emission_factor` records.
- Exchange rates, purchaser/producer conversion ratios and sector price indices remain
  typed `calculation_parameter` source observations.
- Factor activity units encode the model base year and price basis, for example
  `USD_2023_producer_price`.
- Consumers must convert activity spend to model-base-year USD producer price before
  applying a factor; Atlas does not silently perform or assume this conversion.
- Release year, model base year and calculation-parameter reference year remain separate.
- Country rows are `country_modelled`; regional averages are `regional` and apply only to
  countries explicitly listed in the source mapping; Rest of World is an explicit `proxy`.
- Provenance records workbook, sheet, row, column number and sector/country column name for
  both factors and calculation parameters.
- Workbook structure, metadata, sector count and country count are exact parser contracts;
  drift fails ingestion and requires a new parser version.

## Consequences

- Spend calculations remain dimensionally explicit and reproducible.
- Calculation inputs are queryable for a future deterministic spend-conversion service
  without polluting the emission-factor matching catalog.
- Regional and proxy fallback remain visible to matching policy and end users.
- New Open CEDA releases with schema changes require snapshot fixtures and deliberate
  parser-version registration.
