<?php

namespace Tests\Unit\Infrastructure\Candidate;

use App\Application\Candidate\BuildCanonicalCandidateEntity;
use App\Application\Candidate\BuildV2CandidateEntity;
use App\Application\Candidate\ResolveCandidateCatalogMappings;
use App\Application\Contracts\GeographyCatalogResolver;
use App\Application\Contracts\UnitCatalogResolver;
use App\Domain\Candidate\CandidateEntityDraft;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use App\Domain\Candidate\NormalizationContext;
use App\Domain\Catalog\CatalogResolution;
use App\Domain\Catalog\CatalogResolutionStatus;
use App\Domain\Ingestion\ParsedObservation;
use App\Infrastructure\Candidate\NdjsonCandidateEntityMemberWriter;
use App\Infrastructure\Candidate\Rfc8785CanonicalJson;
use App\Infrastructure\Contracts\OpisCandidateSchemaValidator;
use App\Infrastructure\Contracts\PinnedCandidateContractRegistry;
use App\Infrastructure\Sources\Ademe\AdemeCandidateNormalizer;
use App\Infrastructure\Sources\Ademe\AdemeCsvParser;
use DateTimeImmutable;
use Tests\TestCase;

final class NdjsonCandidateEntityMemberWriterTest extends TestCase
{
    public function test_writes_the_same_canonical_v2_member_for_the_same_draft(): void
    {
        $writer = $this->writer();
        $draft = $this->draft();

        $first = $writer->write([$draft]);
        $second = $writer->write([$draft]);

        try {
            $record = json_decode(trim(file_get_contents($first->temporaryPath)), true, flags: JSON_THROW_ON_ERROR);
            $this->assertSame($first->sha256, $second->sha256);
            $this->assertSame(file_get_contents($first->temporaryPath), file_get_contents($second->temporaryPath));
            $this->assertSame('entities.ndjson', $first->path);
            $this->assertSame(1, $first->recordCount);
            $this->assertSame('2.0.0', $record['schema_version']);
            $this->assertMatchesRegularExpression('/^[a-f0-9]{64}$/', $record['record_sha256']);
        } finally {
            unlink($first->temporaryPath);
            unlink($second->temporaryPath);
        }
    }

    public function test_rejects_a_duplicate_candidate_identity(): void
    {
        $draft = $this->draft();

        $this->expectException(CandidateContractViolation::class);
        $this->expectExceptionMessage("Duplicate candidate key {$draft->candidateKey}.");

        $this->writer()->write([$draft, $draft]);
    }

    private function writer(): NdjsonCandidateEntityMemberWriter
    {
        $unresolved = new class implements GeographyCatalogResolver, UnitCatalogResolver
        {
            public function resolveCountry(?string $rawCode, ?string $rawLabel): CatalogResolution
            {
                return new CatalogResolution(CatalogResolutionStatus::Unresolved, null, [], []);
            }

            public function resolve(?string $rawValue): CatalogResolution
            {
                return new CatalogResolution(CatalogResolutionStatus::Unresolved, null, [], []);
            }
        };
        $registry = new PinnedCandidateContractRegistry(
            base_path('resources/contracts/netzero-admin/candidate-v2/contract-manifest.json'),
        );
        $canonical = new BuildCanonicalCandidateEntity(
            new Rfc8785CanonicalJson,
            new OpisCandidateSchemaValidator($registry),
        );

        return new NdjsonCandidateEntityMemberWriter(
            new BuildV2CandidateEntity(
                new ResolveCandidateCatalogMappings($unresolved, $unresolved),
                $canonical,
            ),
        );
    }

    private function draft(): CandidateEntityDraft
    {
        $fields = array_replace(array_fill_keys(AdemeCsvParser::EXPECTED_HEADERS, ''), [
            'Type Ligne' => 'Elément',
            "Identifiant de l'élément" => '100',
            "Type de l'élément" => "Facteur d'émission",
            "Statut de l'élément" => 'Valide générique',
            'Nom base français' => 'Électricité',
            'Code de la catégorie' => '1 > 2',
            'Unité français' => 'kgCO2e/kWh',
            'Localisation géographique' => 'France continentale',
            'Période de validité' => '2024',
            'Total poste non décomposé' => '1,25',
        ]);
        $observation = new ParsedObservation(
            sourceRow: 2,
            recordType: 'Elément',
            sourceRecordId: '100',
            elementType: "Facteur d'émission",
            status: 'Valide générique',
            rowSha256: hash('sha256', json_encode($fields, JSON_THROW_ON_ERROR)),
            fields: $fields,
        );
        $context = new NormalizationContext(
            sourceCode: 'ADEME',
            datasetId: 'base-carboner',
            releaseVersion: '23.6',
            rawAssetKey: 'sources/ademe/raw/Base_Carbone_V23.6.csv',
            rawAssetSha256: str_repeat('a', 64),
            parserVersion: '1.0.0',
            candidateSchemaVersion: '2.0.0',
            retrievedAt: new DateTimeImmutable('2026-09-05T12:00:00Z'),
        );
        $result = (new AdemeCandidateNormalizer)->normalize([$observation], $context);

        return iterator_to_array($result->candidates, false)[0];
    }
}
