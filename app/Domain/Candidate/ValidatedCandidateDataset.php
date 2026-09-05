<?php

namespace App\Domain\Candidate;

final readonly class ValidatedCandidateDataset
{
    public function __construct(public CandidateValidationReceipt $receipt, public CandidateArchiveMember $findings) {}
}
