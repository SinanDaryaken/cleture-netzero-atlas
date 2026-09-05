<?php

namespace App\Application\Candidate;

use App\Application\Contracts\GeographyCatalogResolver;
use App\Application\Contracts\UnitCatalogResolver;
use App\Domain\Candidate\CandidateEntityDraft;

final readonly class ResolveCandidateCatalogMappings
{
    public function __construct(
        private GeographyCatalogResolver $geographies,
        private UnitCatalogResolver $units,
    ) {}

    public function handle(CandidateEntityDraft $draft): CandidateEntityDraft
    {
        return new CandidateEntityDraft(
            schemaVersion: $draft->schemaVersion,
            candidateKey: $draft->candidateKey,
            logicalKey: $draft->logicalKey,
            variantKey: $draft->variantKey,
            valueKind: $draft->valueKind,
            intendedUse: $draft->intendedUse,
            localizedTexts: $draft->localizedTexts,
            sourceTaxonomy: $draft->sourceTaxonomy,
            primaryComponentKey: $draft->primaryComponentKey,
            primaryQuantity: $draft->primaryQuantity,
            components: $draft->components,
            temporal: $draft->temporal,
            methodology: $draft->methodology,
            geographyProposals: array_map($this->resolveGeography(...), $draft->geographyProposals),
            canonicalMappingProposals: array_map($this->resolveMapping(...), $draft->canonicalMappingProposals),
            reportingApplicabilityProposals: $draft->reportingApplicabilityProposals,
            relationships: $draft->relationships,
            evidence: $draft->evidence,
            provenance: $draft->provenance,
            extensions: $draft->extensions,
        );
    }

    /**
     * @param  array<string, mixed>  $proposal
     * @return array<string, mixed>
     */
    private function resolveGeography(array $proposal): array
    {
        if (($proposal['status'] ?? null) !== 'unresolved'
            || ($proposal['target'] ?? null) !== null
            || ($proposal['role'] ?? null) !== 'market'
        ) {
            return $proposal;
        }

        $resolution = $this->geographies->resolveCountry(
            is_string($proposal['raw_code'] ?? null) ? $proposal['raw_code'] : null,
            is_string($proposal['raw_label'] ?? null) ? $proposal['raw_label'] : null,
        );

        $proposal['status'] = $resolution->status->value;
        $proposal['target'] = $resolution->target;

        return $proposal;
    }

    /**
     * @param  array<string, mixed>  $proposal
     * @return array<string, mixed>
     */
    private function resolveMapping(array $proposal): array
    {
        if (($proposal['domain'] ?? null) !== 'unit'
            || ($proposal['status'] ?? null) !== 'unresolved'
            || ($proposal['target'] ?? null) !== null
        ) {
            return $proposal;
        }

        $resolution = $this->units->resolve(
            is_string($proposal['source_value'] ?? null) ? $proposal['source_value'] : null,
        );
        $proposal['status'] = $resolution->status->value;
        $proposal['target'] = $resolution->target;

        return $proposal;
    }
}
