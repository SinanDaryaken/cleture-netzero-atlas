<?php

namespace App\Application\Contracts;

use App\Domain\Candidate\CandidatePackageContext;

interface CandidatePackageIdentityLedger
{
    public function reserve(string $idempotencyKey, CandidatePackageContext $context): CandidatePackageContext;
}
