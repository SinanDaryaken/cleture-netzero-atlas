from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

import yaml

from atlas.domain.enums import ProvenanceRole
from atlas.domain.models import (
    CanonicalFactor,
    FactorProvenance,
    RawAssetReference,
    SourceObservation,
)
from sources.unfccc_tuik.curator import UnfcccTuikCurator
from sources.unfccc_tuik.parser import UnfcccTuikRow


class UnfcccTuikNormalizer:
    def __init__(self, mappings_path: Path) -> None:
        with mappings_path.open(encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        if not isinstance(payload, dict):
            raise ValueError(f"UNFCCC/TÜİK mappings must contain an object: {mappings_path}")
        self.mapping_version = str(payload["version"])
        self.sectors: dict[str, str] = dict(payload["sectors"])
        self.curator = UnfcccTuikCurator(self.sectors, self.mapping_version)

    def normalize(
        self,
        rows: tuple[UnfcccTuikRow, ...],
        *,
        raw: RawAssetReference,
        dataset_revision: str,
        parser_version: str,
    ) -> tuple[
        tuple[SourceObservation, ...],
        tuple[CanonicalFactor, ...],
        dict[str, int],
    ]:
        observations = tuple(
            self._observation(row, raw=raw, parser_version=parser_version) for row in rows
        )
        factors, curation_metrics = self.curator.curate(
            rows,
            raw=raw,
            dataset_revision=dataset_revision,
            parser_version=parser_version,
        )
        entity_counts = Counter(observation.entity_type.value for observation in observations)
        return observations, factors, {
            "source_observations": len(observations),
            "normalized_factors": len(factors),
            "excluded_rows": 0,
            "default_match_eligible": sum(factor.default_match_eligible for factor in factors),
            **{
                f"observation_{entity_type}": count
                for entity_type, count in entity_counts.items()
            },
            **curation_metrics,
        }

    def _observation(
        self,
        row: UnfcccTuikRow,
        *,
        raw: RawAssetReference,
        parser_version: str,
    ) -> SourceObservation:
        identity = "|".join(
            (
                str(row.reference_year),
                row.source_sheet,
                str(row.source_row),
                str(row.source_column),
                row.entity_type.value,
            )
        )
        identity_hash = hashlib.sha256(identity.encode()).hexdigest()[:24]
        return SourceObservation(
            observation_id=f"unfccc-tuik:observation:{identity_hash}",
            entity_type=row.entity_type,
            name=f"{row.category_path} — {row.column_label}",
            value=row.value,
            unit=row.unit,
            reference_year=row.reference_year,
            gas=row.gas,
            source_category=row.category_path,
            source_subcategory=row.column_label,
            provenance=FactorProvenance(
                role=ProvenanceRole.TOTAL,
                raw_asset_key=raw.object_key,
                original_url=raw.source_url,
                downloaded_at=raw.downloaded_at,
                file_checksum=row.member_sha256,
                original_file=row.member_filename,
                parser_version=parser_version,
                mapping_version=self.mapping_version,
                sheet=row.source_sheet,
                table=row.schema_family,
                row=row.source_row,
                original_factor_name=f"{row.category_path} / {row.column_label}",
                original_unit=row.unit,
            ),
            attributes={
                "submission_year": row.submission_year,
                "submission_status": row.submission_status,
                "schema_family": row.schema_family,
                "source_column": row.source_column,
                "activity_unit": row.activity_unit,
                "member_filename": row.member_filename,
            },
        )
