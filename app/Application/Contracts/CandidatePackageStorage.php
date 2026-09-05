<?php

namespace App\Application\Contracts;

use App\Domain\Candidate\CandidatePackageBuild;
use App\Domain\Candidate\StoredCandidatePackage;

interface CandidatePackageStorage
{
    public function store(CandidatePackageBuild $package): StoredCandidatePackage;
}
