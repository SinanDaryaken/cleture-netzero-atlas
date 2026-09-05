<?php

namespace Tests\Unit\Infrastructure\Contracts;

use App\Application\Candidate\BuildCanonicalCandidateEntity;
use App\Domain\Candidate\CandidateContract;
use App\Domain\Candidate\CandidateEntityDraft;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use App\Domain\Candidate\NormalizationContext;
use App\Domain\Ingestion\ParsedObservation;
use App\Infrastructure\Candidate\Rfc8785CanonicalJson;
use App\Infrastructure\Contracts\OpisCandidateSchemaValidator;
use App\Infrastructure\Contracts\PinnedCandidateContractRegistry;
use App\Infrastructure\Sources\Ademe\AdemeCandidateNormalizer;
use App\Infrastructure\Sources\Ademe\AdemeCsvParser;
use DateTimeImmutable;
use Tests\TestCase;

final class OpisCandidateSchemaValidatorTest extends TestCase
{
    public function test_accepts_a_canonical_ademe_candidate_that_matches_the_pinned_entity_schema(): void
    {
        $registry = $this->registry();
        $validator = new OpisCandidateSchemaValidator($registry);
        $builder = new BuildCanonicalCandidateEntity(new Rfc8785CanonicalJson, $validator);
        $draft = $this->ademeDraft();

        $entity = $builder->handle($draft);

        $this->assertSame($draft->candidateKey, $entity->candidateKey);
        $this->assertSame($entity->recordSha256, $entity->record['record_sha256']);
        $this->assertStringStartsWith('{', $entity->canonicalJson);
    }

    public function test_rejects_a_candidate_that_violates_the_pinned_entity_schema(): void
    {
        $registry = $this->registry();
        $validator = new OpisCandidateSchemaValidator($registry);
        $record = (new BuildCanonicalCandidateEntity(new Rfc8785CanonicalJson, $validator))
            ->handle($this->ademeDraft())
            ->record;
        $record['components'] = [];

        $this->expectException(CandidateContractViolation::class);
        $this->expectExceptionMessage('Candidate candidate_entity_record failed JSON Schema validation');

        $validator->assertValid(CandidateContract::EntityRecord, $record);
    }

    public function test_accepts_an_ademe_candidate_against_the_separate_v2_entity_contract(): void
    {
        $registry = new PinnedCandidateContractRegistry(
            base_path('resources/contracts/netzero-admin/candidate-v2/contract-manifest.json'),
        );
        $validator = new OpisCandidateSchemaValidator($registry);
        $builder = new BuildCanonicalCandidateEntity(new Rfc8785CanonicalJson, $validator);

        $entity = $builder->handle($this->ademeDraft('2.0.0'));

        $this->assertSame('2.0.0', $entity->record['schema_version']);
        $this->assertSame($entity->recordSha256, $entity->record['record_sha256']);
    }

    public function test_v2_relationship_contract_rejects_every_standalone_record(): void
    {
        $registry = new PinnedCandidateContractRegistry(
            base_path('resources/contracts/netzero-admin/candidate-v2/contract-manifest.json'),
        );
        $validator = new OpisCandidateSchemaValidator($registry);

        $this->expectException(CandidateContractViolation::class);
        $this->expectExceptionMessage('Candidate candidate_relationship_record failed JSON Schema validation');

        $validator->assertValid(CandidateContract::RelationshipRecord, []);
    }

    private function registry(): PinnedCandidateContractRegistry
    {
        return new PinnedCandidateContractRegistry(
            base_path('resources/contracts/netzero-admin/candidate-v1/contract-manifest.json'),
        );
    }

    private function ademeDraft(string $candidateSchemaVersion = '1.0.0'): CandidateEntityDraft
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
            candidateSchemaVersion: $candidateSchemaVersion,
            retrievedAt: new DateTimeImmutable('2026-09-04T12:00:00Z'),
        );
        $result = (new AdemeCandidateNormalizer)->normalize([$observation], $context);

        return iterator_to_array($result->candidates, false)[0];
    }
}
