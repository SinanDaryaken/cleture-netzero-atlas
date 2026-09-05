<?php

namespace App\Application\Candidate;

use App\Application\Contracts\CandidateContractRegistry;
use App\Application\Contracts\CandidateDraftReader;
use App\Application\Contracts\CandidateEntityMemberWriter;
use App\Domain\Candidate\CandidateArchiveMember;
use App\Domain\Candidate\CandidateContract;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use App\Domain\Candidate\StoredNormalizedArtifact;

final readonly class BuildCandidateEntityMemberFromArtifact
{
    public function __construct(
        private CandidateContractRegistry $contracts,
        private CandidateDraftReader $drafts,
        private CandidateEntityMemberWriter $writer,
    ) {}

    public function handle(StoredNormalizedArtifact $artifact): CandidateArchiveMember
    {
        $entityContract = $this->contracts->get(CandidateContract::EntityRecord);

        if ($entityContract->version !== '2.0.0'
            || $artifact->candidateSchemaVersion !== $entityContract->version
            || ! hash_equals($entityContract->sha256, $artifact->candidateSchemaSha256)
        ) {
            throw new CandidateContractViolation('Normalized artifact is not pinned to the active candidate V2 entity contract.');
        }

        return $this->writer->write($this->drafts->read($artifact));
    }
}
