<?php

namespace App\Application\Contracts;

use App\Domain\Candidate\CandidatePackageBuild;
use App\Domain\Candidate\CandidatePackageContext;
use App\Domain\Candidate\RegisteredCandidatePackage;
use App\Domain\Candidate\StoredCandidatePackage;

interface CandidatePackageLedger
{
    public function register(
        CandidatePackageContext $context,
        CandidatePackageBuild $package,
        StoredCandidatePackage $storage,
    ): RegisteredCandidatePackage;
}
