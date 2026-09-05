<?php

namespace App\Application\Contracts;

use App\Domain\Candidate\CandidateArchiveMember;
use App\Domain\Candidate\CanonicalCandidateEntity;

interface CandidateEntityReader
{
    /** @return iterable<CanonicalCandidateEntity> */
    public function read(CandidateArchiveMember $member): iterable;
}
