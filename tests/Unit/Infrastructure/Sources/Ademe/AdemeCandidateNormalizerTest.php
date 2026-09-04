<?php

namespace Tests\Unit\Infrastructure\Sources\Ademe;

use App\Domain\Candidate\NormalizationContext;
use App\Domain\Ingestion\Exceptions\SourceContractViolation;
use App\Domain\Ingestion\ParsedObservation;
use App\Infrastructure\Sources\Ademe\AdemeCandidateNormalizer;
use App\Infrastructure\Sources\Ademe\AdemeCsvParser;
use DateTimeImmutable;
use Tests\TestCase;

final class AdemeCandidateNormalizerTest extends TestCase
{
    public function test_builds_an_unresolved_candidate_with_gas_and_lifecycle_components(): void
    {
        $element = $this->observation(2, 'Elément', [
            'Nom base français' => 'Électricité',
            'Nom attribut français' => 'France',
            'Code de la catégorie' => '1 > 2',
            'Unité français' => 'kgCO2e/kWh',
            'Localisation géographique' => 'France continentale',
            'Période de validité' => 'Année 2024',
            'Total poste non décomposé' => '1,2500',
            'CO2f' => '1,0',
            'Code gaz supplémentaire 1' => 'HFC-134a',
            'Valeur gaz supplémentaire 1' => '2.5e-2',
        ]);
        $post = $this->observation(3, 'Poste', [
            'Type poste' => 'Amont',
            'Nom poste français' => 'Fabrication',
            'Total poste non décomposé' => '0,25',
            'CH4f' => '0,01',
        ]);

        $result = (new AdemeCandidateNormalizer)->normalize([$element, $post], $this->context());
        $candidates = iterator_to_array($result->candidates, false);
        $record = $candidates[0]->toUnhashedRecord();

        $this->assertCount(1, $candidates);
        $this->assertSame([], $result->findings);
        $this->assertSame('1.25', $record['primary_quantity']['value']);
        $this->assertSame('source_unspecified', $record['intended_use'][0]);
        $this->assertSame('unresolved', $record['geography_proposals'][0]['status']);
        $this->assertNull($record['geography_proposals'][0]['target']);
        $this->assertSame('kgCO2e/kWh', $record['canonical_mapping_proposals'][0]['source_value']);
        $this->assertCount(5, $record['components']);
        $this->assertSame('CO2_fossil', $record['components'][1]['gas_code']);
        $this->assertSame('0.025', $record['components'][2]['quantity']['value']);
        $this->assertSame('lifecycle_stage', $record['components'][3]['basis']);
        $this->assertSame('lifecycle_stage_gas_component', $record['components'][4]['basis']);
        $this->assertSame('CH4_fossil', $record['components'][4]['gas_code']);
        $this->assertCount(2, $record['evidence']);
        $this->assertCount(2, $record['provenance']);
        $this->assertSame((object) [], $record['extensions']);
        $this->assertArrayNotHasKey('record_sha256', $record);
        $this->assertSame(1, $result->metrics['attached_post_observations']);
    }

    public function test_preserves_a_negative_total_without_assigning_avoided_emission_semantics(): void
    {
        $negative = $this->observation(2, 'Elément', [
            'Total poste non décomposé' => '-2,500',
            'Unité français' => 'kgCO2e/unité',
        ]);
        $archived = $this->observation(3, 'Elément', [
            "Statut de l'élément" => 'Archivé',
        ]);
        $sourceData = $this->observation(4, 'Elément', [
            "Type de l'élément" => 'Données source',
        ]);

        $result = (new AdemeCandidateNormalizer)->normalize(
            [$negative, $archived, $sourceData],
            $this->context(),
        );
        $candidates = iterator_to_array($result->candidates, false);
        $record = $candidates[0]->toUnhashedRecord();

        $this->assertCount(1, $candidates);
        $this->assertSame('-2.5', $record['primary_quantity']['value']);
        $this->assertSame(['source_unspecified'], $record['intended_use']);
        $this->assertSame('negative_total_requires_methodology_review', $result->findings[0]->code);
        $this->assertSame('review', $result->findings[0]->severity);
        $this->assertSame(1, $result->metrics['negative_totals_requiring_review']);
        $this->assertSame(2, $result->metrics['skipped_non_candidate_observations']);
    }

    public function test_rejects_a_foreign_dataset_context(): void
    {
        $context = new NormalizationContext(
            sourceCode: 'ADEME',
            datasetId: 'different-dataset',
            releaseVersion: '23.6',
            rawAssetKey: 'sources/ademe/raw.csv',
            rawAssetSha256: str_repeat('a', 64),
            parserVersion: '1.0.0',
            retrievedAt: new DateTimeImmutable('2026-09-04T12:00:00+03:00'),
        );

        $this->expectException(SourceContractViolation::class);
        $this->expectExceptionMessage('ADEME normalizer received a foreign source context.');

        (new AdemeCandidateNormalizer)->normalize([], $context);
    }

    /** @param array<string, string> $overrides */
    private function observation(int $sourceRow, string $recordType, array $overrides = []): ParsedObservation
    {
        $fields = array_replace(array_fill_keys(AdemeCsvParser::EXPECTED_HEADERS, ''), [
            'Type Ligne' => $recordType,
            "Identifiant de l'élément" => '100',
            "Type de l'élément" => "Facteur d'émission",
            "Statut de l'élément" => 'Valide générique',
            'Nom base français' => 'Facteur test',
        ], $overrides);

        return new ParsedObservation(
            sourceRow: $sourceRow,
            recordType: $recordType,
            sourceRecordId: $fields["Identifiant de l'élément"],
            elementType: $fields["Type de l'élément"],
            status: $fields["Statut de l'élément"],
            rowSha256: hash('sha256', json_encode($fields, JSON_THROW_ON_ERROR)),
            fields: $fields,
        );
    }

    private function context(): NormalizationContext
    {
        return new NormalizationContext(
            sourceCode: 'ADEME',
            datasetId: 'base-carboner',
            releaseVersion: '23.6',
            rawAssetKey: 'sources/ademe/raw/Base_Carbone_V23.6.csv',
            rawAssetSha256: str_repeat('a', 64),
            parserVersion: '1.0.0',
            retrievedAt: new DateTimeImmutable('2026-09-04T12:00:00+03:00'),
            sourcePublishedAt: new DateTimeImmutable('2025-07-03T08:07:23Z'),
        );
    }
}
