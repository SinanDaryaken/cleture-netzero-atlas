<?php

namespace App\Domain\Candidate;

final readonly class CandidateBuildResult
{
    public function __construct(public CandidateValidationReceipt $validation, public ?RegisteredCandidatePackage $package) {}
}
