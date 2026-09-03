# ADR 0015 — Multi-asset acquisition bundles

## Status

Accepted — 2026-08-28

## Context

Some source releases are a coherent dataset made from several independently published
files. AGRIBALYSE 3.2 publishes separate conventional agriculture, organic agriculture
and food-product result workbooks. Processing only one file would make the dataset
incomplete; flattening or rewriting them before raw storage would break auditability.

The initial pipeline has one raw object boundary per source run. Expanding every pipeline
contract to an unordered asset list would also make change detection and idempotency
ambiguous.

## Decision

A multi-file release may be stored as a deterministic acquisition bundle when all of the
following hold:

- every publisher asset is included byte-for-byte and never edited;
- the bundle contains a machine-readable manifest with role, original URL, byte size and
  member SHA256;
- bundle member order, timestamps and compression settings are deterministic;
- change detection uses the stable member manifest, not download time;
- row provenance points to the original member filename, URL and member checksum while
  also linking to the immutable raw bundle object;
- generated bundles are explicitly marked `acquisition_bundle` in raw metadata and are
  never represented as publisher-authored archives.

Parser outputs and normalized Parquet files remain processing artifacts, not raw assets.

## Consequences

- A release has one idempotent dataset-version boundary without losing original files.
- Atlas can later add first-class multi-asset rows without changing factor provenance.
- A source adapter must reject missing members and checksum mismatches before parsing.
- Public/open result files do not grant rights to restricted background inventories;
  AGRIBALYSE ecoinvent background data is outside the ingestion boundary.
