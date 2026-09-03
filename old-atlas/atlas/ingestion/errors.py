class AtlasIngestionError(Exception):
    """Base class for classified ingestion failures."""


class RetryableIngestionError(AtlasIngestionError):
    """Transient infrastructure/source failure eligible for bounded retry."""


class PermanentIngestionError(AtlasIngestionError):
    """Schema, parser, license, or validation failure that retry cannot fix."""
