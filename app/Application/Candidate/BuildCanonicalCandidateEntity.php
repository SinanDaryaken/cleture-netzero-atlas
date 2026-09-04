<?php

namespace App\Application\Candidate;

use App\Application\Contracts\CandidateSchemaValidator;
use App\Application\Contracts\CanonicalJson;
use App\Domain\Candidate\CandidateContract;
use App\Domain\Candidate\CandidateEntityDraft;
use App\Domain\Candidate\CanonicalCandidateEntity;

final readonly class BuildCanonicalCandidateEntity
{
    public function __construct(
        private CanonicalJson $canonicalJson,
        private CandidateSchemaValidator $schemaValidator,
    ) {}

    public function handle(CandidateEntityDraft $draft): CanonicalCandidateEntity
    {
        $unhashedRecord = $draft->toUnhashedRecord();
        $recordSha256 = hash('sha256', $this->canonicalJson->encode($unhashedRecord));
        $record = [
            'schema_version' => $unhashedRecord['schema_version'],
            'candidate_key' => $unhashedRecord['candidate_key'],
            'logical_key' => $unhashedRecord['logical_key'],
            'variant_key' => $unhashedRecord['variant_key'],
            'record_sha256' => $recordSha256,
            ...array_slice($unhashedRecord, 4, preserve_keys: true),
        ];

        $entity = new CanonicalCandidateEntity(
            candidateKey: $draft->candidateKey,
            recordSha256: $recordSha256,
            record: $record,
            canonicalJson: $this->canonicalJson->encode($record),
        );
        $this->schemaValidator->assertValid(CandidateContract::EntityRecord, $entity->record);

        return $entity;
    }
}
