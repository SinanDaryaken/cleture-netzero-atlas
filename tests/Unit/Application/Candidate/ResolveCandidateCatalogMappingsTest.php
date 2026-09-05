<?php

namespace Tests\Unit\Application\Candidate;

use App\Application\Candidate\ResolveCandidateCatalogMappings;
use App\Application\Contracts\GeographyCatalogResolver;
use App\Application\Contracts\UnitCatalogResolver;
use App\Domain\Candidate\CandidateEntityDraft;
use App\Domain\Catalog\CatalogResolution;
use App\Domain\Catalog\CatalogResolutionStatus;
use Tests\TestCase;

final class ResolveCandidateCatalogMappingsTest extends TestCase
{
    public function test_applies_only_unique_catalog_proposals_and_preserves_unresolved_values(): void
    {
        $geography = new class implements GeographyCatalogResolver
        {
            public function resolveCountry(?string $rawCode, ?string $rawLabel): CatalogResolution
            {
                return new CatalogResolution(
                    CatalogResolutionStatus::Proposed,
                    [
                        'owner' => 'NetZeroAdmin',
                        'canonical_geography_id' => '01a00000-0000-7000-8000-000000000001',
                        'entity_level' => 'country',
                        'catalog_version' => 'sha256:'.str_repeat('a', 64),
                        'catalog_sha256' => str_repeat('a', 64),
                    ],
                    ['01a00000-0000-7000-8000-000000000001'],
                    ['name:fr'],
                );
            }
        };
        $unit = new class implements UnitCatalogResolver
        {
            public function resolve(?string $rawValue): CatalogResolution
            {
                return new CatalogResolution(CatalogResolutionStatus::Unresolved, null, [], []);
            }
        };
        $draft = $this->draft();

        $resolved = (new ResolveCandidateCatalogMappings($geography, $unit))->handle($draft);

        $this->assertSame('proposed', $resolved->geographyProposals[0]['status']);
        $this->assertSame(
            '01a00000-0000-7000-8000-000000000001',
            $resolved->geographyProposals[0]['target']['canonical_geography_id'],
        );
        $this->assertSame('unresolved', $resolved->canonicalMappingProposals[0]['status']);
        $this->assertNull($resolved->canonicalMappingProposals[0]['target']);
        $this->assertSame($draft->candidateKey, $resolved->candidateKey);
    }

    private function draft(): CandidateEntityDraft
    {
        return new CandidateEntityDraft(
            schemaVersion: '2.0.0',
            candidateKey: 'candidate-1',
            logicalKey: 'logical-1',
            variantKey: 'variant-1',
            valueKind: 'co2e_total',
            intendedUse: ['source_unspecified'],
            localizedTexts: [['locale' => 'fr']],
            sourceTaxonomy: [['scheme' => 'ADEME']],
            primaryComponentKey: 'component-1',
            primaryQuantity: [],
            components: [['component_key' => 'component-1']],
            temporal: [],
            methodology: [],
            geographyProposals: [[
                'proposal_key' => 'geography-1',
                'role' => 'market',
                'raw_code' => null,
                'raw_label' => 'France',
                'status' => 'unresolved',
                'target' => null,
            ]],
            canonicalMappingProposals: [[
                'proposal_key' => 'unit-1',
                'domain' => 'unit',
                'source_value' => 'kgCO2e/kWh',
                'status' => 'unresolved',
                'target' => null,
            ]],
            reportingApplicabilityProposals: [],
            relationships: [],
            evidence: [['evidence_key' => 'evidence-1']],
            provenance: [['provenance_key' => 'provenance-1']],
            extensions: [],
        );
    }
}
