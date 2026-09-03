# ADR 0016: National inventory submission time is separate from inventory time

## Status

Accepted.

## Context

An annual UNFCCC CRF/CRT submission is not one annual factor file. A Türkiye
submission ZIP contains one structured workbook for every inventory reference year
covered by that submission. Later submissions can revise earlier inventory years.
The 2020 submission contains 1990–2018, while the 2024 submission contains 1990–2022.

## Decision

- `release_year` identifies the UNFCCC submission year.
- `reference_year` identifies the inventory year of the member workbook.
- Each outer ZIP is one immutable dataset version and each member workbook checksum is
  retained in raw metadata and row-level provenance.
- CRF 2020–2023 and CRT 2024–2026 use independent parser families.
- Source publication state such as `started` or `awaiting_submission` is retained as
  provenance and forces review. Human approval publishes the candidate but never
  rewrites that source state to `submitted`.
- Backfills and approvals run from oldest submission to newest so a later historical
  revision becomes current while the earlier value remains queryable with `known_at`.

## Consequences

Atlas can answer both “what is the current revised value for inventory year 2018?” and
“what did the 2020 submission report for inventory year 2018?”. A synthetic single
`year` column cannot represent this distinction and is prohibited for national
inventory submissions.
