<?php

namespace App\Application\Contracts;

use App\Domain\Candidate\CandidateEntityDraft;
use App\Domain\Candidate\StoredNormalizedArtifact;

interface CandidateDraftReader
{
    /** @return iterable<CandidateEntityDraft> */
    public function read(StoredNormalizedArtifact $artifact): iterable;
}
