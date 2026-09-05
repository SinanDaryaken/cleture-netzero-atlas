<?php

namespace App\Domain\Candidate;

use InvalidArgumentException;

final readonly class CandidateEntityDraft
{
    private const RECORD_KEYS = [
        'schema_version',
        'candidate_key',
        'logical_key',
        'variant_key',
        'entity_type',
        'value_kind',
        'intended_use',
        'localized_texts',
        'source_taxonomy',
        'primary_component_key',
        'primary_quantity',
        'components',
        'temporal',
        'methodology',
        'geography_proposals',
        'canonical_mapping_proposals',
        'reporting_applicability_proposals',
        'relationships',
        'evidence',
        'provenance',
        'extensions',
    ];

    /**
     * @param  non-empty-list<string>  $intendedUse
     * @param  non-empty-list<array<string, mixed>>  $localizedTexts
     * @param  non-empty-list<array<string, mixed>>  $sourceTaxonomy
     * @param  array<string, mixed>  $primaryQuantity
     * @param  non-empty-list<array<string, mixed>>  $components
     * @param  array<string, mixed>  $temporal
     * @param  array<string, mixed>  $methodology
     * @param  list<array<string, mixed>>  $geographyProposals
     * @param  list<array<string, mixed>>  $canonicalMappingProposals
     * @param  list<array<string, mixed>>  $reportingApplicabilityProposals
     * @param  list<string>  $relationships
     * @param  non-empty-list<array<string, mixed>>  $evidence
     * @param  non-empty-list<array<string, mixed>>  $provenance
     * @param  array<string, mixed>  $extensions
     */
    public function __construct(
        public string $schemaVersion,
        public string $candidateKey,
        public string $logicalKey,
        public string $variantKey,
        public string $valueKind,
        public array $intendedUse,
        public array $localizedTexts,
        public array $sourceTaxonomy,
        public string $primaryComponentKey,
        public array $primaryQuantity,
        public array $components,
        public array $temporal,
        public array $methodology,
        public array $geographyProposals,
        public array $canonicalMappingProposals,
        public array $reportingApplicabilityProposals,
        public array $relationships,
        public array $evidence,
        public array $provenance,
        public array $extensions,
    ) {
        foreach ([$this->schemaVersion, $this->candidateKey, $this->logicalKey, $this->variantKey, $this->primaryComponentKey] as $identity) {
            if ($identity === '' || preg_match('/[\x00-\x1F\x7F]/', $identity) === 1) {
                throw new InvalidArgumentException('Candidate draft identity is invalid.');
            }
        }

        if ($this->intendedUse === [] || $this->localizedTexts === [] || $this->sourceTaxonomy === []
            || $this->components === [] || $this->evidence === [] || $this->provenance === []
        ) {
            throw new InvalidArgumentException('Candidate draft required collections cannot be empty.');
        }
    }

    /** @param array<string, mixed> $record */
    public static function fromUnhashedRecord(array $record): self
    {
        $keys = array_keys($record);
        sort($keys, SORT_STRING);
        $expectedKeys = self::RECORD_KEYS;
        sort($expectedKeys, SORT_STRING);

        if ($keys !== $expectedKeys || ($record['entity_type'] ?? null) !== 'emission_factor') {
            throw new InvalidArgumentException('Candidate draft record shape is invalid.');
        }

        return new self(
            schemaVersion: self::stringField($record, 'schema_version'),
            candidateKey: self::stringField($record, 'candidate_key'),
            logicalKey: self::stringField($record, 'logical_key'),
            variantKey: self::stringField($record, 'variant_key'),
            valueKind: self::stringField($record, 'value_kind'),
            intendedUse: self::arrayField($record, 'intended_use'),
            localizedTexts: self::arrayField($record, 'localized_texts'),
            sourceTaxonomy: self::arrayField($record, 'source_taxonomy'),
            primaryComponentKey: self::stringField($record, 'primary_component_key'),
            primaryQuantity: self::arrayField($record, 'primary_quantity'),
            components: self::arrayField($record, 'components'),
            temporal: self::arrayField($record, 'temporal'),
            methodology: self::arrayField($record, 'methodology'),
            geographyProposals: self::arrayField($record, 'geography_proposals'),
            canonicalMappingProposals: self::arrayField($record, 'canonical_mapping_proposals'),
            reportingApplicabilityProposals: self::arrayField($record, 'reporting_applicability_proposals'),
            relationships: self::arrayField($record, 'relationships'),
            evidence: self::arrayField($record, 'evidence'),
            provenance: self::arrayField($record, 'provenance'),
            extensions: self::arrayField($record, 'extensions'),
        );
    }

    /**
     * The package builder adds record_sha256 after RFC 8785 canonicalization.
     *
     * @return array<string, mixed>
     */
    public function toUnhashedRecord(): array
    {
        return [
            'schema_version' => $this->schemaVersion,
            'candidate_key' => $this->candidateKey,
            'logical_key' => $this->logicalKey,
            'variant_key' => $this->variantKey,
            'entity_type' => 'emission_factor',
            'value_kind' => $this->valueKind,
            'intended_use' => $this->intendedUse,
            'localized_texts' => $this->localizedTexts,
            'source_taxonomy' => $this->sourceTaxonomy,
            'primary_component_key' => $this->primaryComponentKey,
            'primary_quantity' => $this->primaryQuantity,
            'components' => $this->components,
            'temporal' => $this->temporal,
            'methodology' => $this->methodology,
            'geography_proposals' => $this->geographyProposals,
            'canonical_mapping_proposals' => $this->canonicalMappingProposals,
            'reporting_applicability_proposals' => $this->reportingApplicabilityProposals,
            'relationships' => $this->relationships,
            'evidence' => $this->evidence,
            'provenance' => $this->provenance,
            'extensions' => (object) $this->extensions,
        ];
    }

    /** @param array<string, mixed> $record */
    private static function stringField(array $record, string $key): string
    {
        $value = $record[$key] ?? null;

        if (! is_string($value)) {
            throw new InvalidArgumentException("Candidate draft {$key} must be a string.");
        }

        return $value;
    }

    /**
     * @param  array<string, mixed>  $record
     * @return array<mixed>
     */
    private static function arrayField(array $record, string $key): array
    {
        $value = $record[$key] ?? null;

        if (! is_array($value)) {
            throw new InvalidArgumentException("Candidate draft {$key} must be an array.");
        }

        return $value;
    }
}
