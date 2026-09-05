<?php

namespace App\Application\Contracts;

use App\Domain\Candidate\CandidateArchiveMember;

interface PreviousCandidatePackageReader
{
    public function entities(string $packageId, array $source): CandidateArchiveMember;
}
