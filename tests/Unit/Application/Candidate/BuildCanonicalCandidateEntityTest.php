<?php

namespace Tests\Unit\Application\Candidate;

use App\Application\Candidate\BuildCanonicalCandidateEntity;
use App\Application\Contracts\CandidateSchemaValidator;
use App\Application\Contracts\CanonicalJson;
use App\Domain\Candidate\CandidateContract;
use App\Domain\Candidate\CandidateEntityDraft;
use Tests\TestCase;

final class BuildCanonicalCandidateEntityTest extends TestCase
{
    public function test_hashes_the_unhashed_record_before_encoding_the_final_entity(): void
    {
        $canonicalJson = new class implements CanonicalJson
        {
            public int $calls = 0;

            public function encode(mixed $value): string
            {
                $this->calls++;

                if ($this->calls === 1) {
                    if (! is_array($value) || array_key_exists('record_sha256', $value)) {
                        throw new \LogicException('First canonicalization must receive the unhashed record.');
                    }

                    return 'canonical-unhashed-record';
                }

                if (! is_array($value) || ! is_string($value['record_sha256'] ?? null)) {
                    throw new \LogicException('Second canonicalization must receive the final record.');
                }

                return 'canonical-final-record';
            }
        };
        $schemaValidator = new class implements CandidateSchemaValidator
        {
            public ?CandidateContract $contract = null;

            /** @var array<string, mixed>|null */
            public ?array $record = null;

            public function assertValid(CandidateContract $contract, array $record): void
            {
                $this->contract = $contract;
                $this->record = $record;
            }
        };
        $draft = $this->draft();

        $entity = (new BuildCanonicalCandidateEntity($canonicalJson, $schemaValidator))->handle($draft);

        $this->assertSame('candidate-1', $entity->candidateKey);
        $this->assertSame(
            'f1c5297352975c6e9dbf3dee84dc9757b00ea55a90d70f13b865e0f445d8ab4a',
            $entity->recordSha256,
        );
        $this->assertSame($entity->recordSha256, $entity->record['record_sha256']);
        $this->assertSame('canonical-final-record', $entity->canonicalJson);
        $this->assertSame(2, $canonicalJson->calls);
        $this->assertSame(CandidateContract::EntityRecord, $schemaValidator->contract);
        $this->assertSame($entity->record, $schemaValidator->record);
    }

    private function draft(): CandidateEntityDraft
    {
        return new CandidateEntityDraft(
            schemaVersion: '1.0.0',
            candidateKey: 'candidate-1',
            logicalKey: 'logical-1',
            variantKey: 'variant-1',
            valueKind: 'co2e_total',
            intendedUse: ['source_unspecified'],
            localizedTexts: [['locale' => 'fr', 'label' => 'Facteur', 'description' => null]],
            sourceTaxonomy: [['scheme' => 'SOURCE', 'code' => 'CODE']],
            primaryComponentKey: 'component-1',
            primaryQuantity: [],
            components: [['component_key' => 'component-1']],
            temporal: [],
            methodology: [],
            geographyProposals: [],
            canonicalMappingProposals: [],
            reportingApplicabilityProposals: [],
            relationships: [],
            evidence: [['evidence_key' => 'evidence-1']],
            provenance: [['provenance_key' => 'provenance-1']],
            extensions: [],
        );
    }
}
