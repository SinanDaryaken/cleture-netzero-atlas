<?php

namespace Tests\Unit\Application\Candidate;

use App\Application\Candidate\BuildCandidateEntityMemberFromArtifact;
use App\Application\Contracts\CandidateDraftReader;
use App\Application\Contracts\CandidateEntityMemberWriter;
use App\Domain\Candidate\CandidateArchiveMember;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use App\Domain\Candidate\StoredNormalizedArtifact;
use App\Infrastructure\Contracts\PinnedCandidateContractRegistry;
use Tests\TestCase;

final class BuildCandidateEntityMemberFromArtifactTest extends TestCase
{
    public function test_rejects_a_v1_artifact_without_reading_or_downgrading_it(): void
    {
        $reader = new class implements CandidateDraftReader
        {
            public function read(StoredNormalizedArtifact $artifact): iterable
            {
                throw new \LogicException('V1 artifact must not be read.');
            }
        };
        $writer = new class implements CandidateEntityMemberWriter
        {
            public function write(iterable $drafts): CandidateArchiveMember
            {
                throw new \LogicException('V1 artifact must not be written.');
            }
        };
        $builder = new BuildCandidateEntityMemberFromArtifact(
            new PinnedCandidateContractRegistry(
                base_path('resources/contracts/netzero-admin/candidate-v2/contract-manifest.json'),
            ),
            $reader,
            $writer,
        );
        $artifact = new StoredNormalizedArtifact(
            disk: 'atlas_processing',
            objectKey: 'normalized/v1.ndjson',
            format: 'ndjson',
            normalizerVersion: '1.0.0',
            candidateSchemaVersion: '1.0.0',
            candidateSchemaSha256: str_repeat('a', 64),
            candidateCount: 1,
            findingCount: 0,
            fileSize: 1,
            sha256: str_repeat('b', 64),
            alreadyExisted: true,
        );

        $this->expectException(CandidateContractViolation::class);
        $this->expectExceptionMessage('not pinned to the active candidate V2 entity contract');

        $builder->handle($artifact);
    }
}
