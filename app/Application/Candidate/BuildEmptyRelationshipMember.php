<?php

namespace App\Application\Candidate;

use App\Domain\Candidate\CandidateArchiveMember;
use RuntimeException;

final class BuildEmptyRelationshipMember
{
    public function handle(): CandidateArchiveMember
    {
        $temporaryPath = tempnam(sys_get_temp_dir(), 'atlas-v2-relationships-');

        if ($temporaryPath === false) {
            throw new RuntimeException('A temporary V2 relationship member could not be created.');
        }

        return new CandidateArchiveMember(
            path: 'relationships.ndjson',
            temporaryPath: $temporaryPath,
            sha256: hash('sha256', ''),
            sizeBytes: 0,
            recordCount: 0,
        );
    }
}
