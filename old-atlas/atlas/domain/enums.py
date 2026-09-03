from enum import StrEnum


class SourceStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    DISABLED = "disabled"


class SourceHealth(StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    STALE = "stale"
    FAILED = "failed"
    DISABLED = "disabled"


class SourceHistoryStrategy(StrEnum):
    YEARLY_RELEASE = "yearly_release"
    LAGGED_YEARLY_RELEASE = "lagged_yearly_release"
    YEARLY_SUBMISSION = "yearly_submission"
    VERSIONED_DATABASE = "versioned_database"
    API_TIME_SERIES = "api_time_series"
    VERSIONED_DERIVED_DATA = "versioned_derived_data"


class DatasetLayer(StrEnum):
    RAW = "raw"
    PARSED = "parsed"
    NORMALIZED = "normalized"
    VALIDATED = "validated"
    PUBLISHED = "published"


class DatasetVersionStatus(StrEnum):
    DETECTED = "detected"
    RAW = "raw"
    PARSED = "parsed"
    NORMALIZED = "normalized"
    VALIDATED = "validated"
    REVIEW_REQUIRED = "review_required"
    PUBLISHED = "published"
    REJECTED = "rejected"


class TemporalVersionStatus(StrEnum):
    CANDIDATE = "candidate"
    CURRENT = "current"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class OutboxStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    PUBLISHED = "published"
    FAILED = "failed"


class ProvenanceRole(StrEnum):
    TOTAL = "total"
    CO2 = "co2"
    CH4 = "ch4"
    N2O = "n2o"


class PipelineStep(StrEnum):
    CHECK = "check"
    FETCH = "fetch"
    STORE_RAW = "store_raw"
    PARSE = "parse"
    NORMALIZE = "normalize"
    VALIDATE = "validate"
    COMPARE = "compare"
    VERSION = "version"
    PUBLISH = "publish"


PIPELINE_STEPS: tuple[PipelineStep, ...] = tuple(PipelineStep)


class StepStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    WARNING = "warning"
    REVIEW_REQUIRED = "review_required"


class RunOutcome(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    NO_CHANGE = "no_change"
    REVIEW_REQUIRED = "review_required"


class RunMode(StrEnum):
    LATEST = "latest"
    HISTORICAL_BACKFILL = "historical_backfill"


class QualitySeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    FAIL = "fail"
    REVIEW_REQUIRED = "review_required"


class GeographyLevel(StrEnum):
    GLOBAL = "global"
    CONTINENT = "continent"
    REGION = "region"
    COUNTRY = "country"
    STATE = "state"
    PROVINCE = "province"
    CITY = "city"
    GRID = "grid"
    CUSTOM = "custom"


class GeographicFitType(StrEnum):
    COUNTRY_SPECIFIC = "country_specific"
    COUNTRY_MODELLED = "country_modelled"
    REGIONAL = "regional"
    CONTINENTAL = "continental"
    GLOBAL = "global"
    PROXY = "proxy"


class GeographyRole(StrEnum):
    PRODUCTION_ORIGIN = "production_origin"
    MARKET = "market"
    CALCULATION_APPLICABILITY = "calculation_applicability"
    JURISDICTION = "jurisdiction"
    GRID = "grid"
    ROUTE_ORIGIN = "route_origin"
    ROUTE_DESTINATION = "route_destination"


class GeographyDerivation(StrEnum):
    SOURCE_DECLARED = "source_declared"
    VERIFIED_MAPPING = "verified_mapping"


class FactorValueKind(StrEnum):
    CO2E_TOTAL = "co2e_total"
    CO2_ONLY = "co2_only"
    NON_CO2_CO2E = "non_co2_co2e"
    GAS_EMISSION_FACTOR = "gas_emission_factor"
    CALCULATION_PARAMETER = "calculation_parameter"
    CHARACTERIZATION_FACTOR = "characterization_factor"


class FactorIntendedUse(StrEnum):
    INVENTORY = "inventory"
    CALCULATION_INPUT = "calculation_input"
    AVOIDED_EMISSIONS = "avoided_emissions"
    CHARACTERIZATION = "characterization"


class EnvironmentalEntityType(StrEnum):
    EMISSION_FACTOR = "emission_factor"
    IMPLIED_EMISSION_FACTOR = "implied_emission_factor"
    ACTIVITY_DATA = "activity_data"
    EMISSION_RESULT = "emission_result"
    CALCULATION_PARAMETER = "calculation_parameter"
    REFERENCE_VALUE = "reference_value"
    LCA_RESULT = "lca_result"
    CHARACTERIZATION_RESULT = "characterization_result"
    EPD = "epd"
    CONVERSION_FACTOR = "conversion_factor"
    TECHNICAL_PROPERTY = "technical_property"
    EMBODIED_EMISSION_FACTOR = "embodied_emission_factor"
