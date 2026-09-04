<?php

namespace App\Domain\Candidate;

use InvalidArgumentException;

final readonly class CandidateEntityDraft
{
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
}
